from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
from collections import deque
from datetime import timedelta
from pathlib import Path


_LOG = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class InvocationProblem(Exception):
    status: int
    code: str
    detail: str
    request_id: str | None = None
    retriable: bool = False


@dataclass(frozen=True)
class InvocationResult:
    status: int
    headers: tuple[tuple[bytes, bytes], ...]
    body: bytes
    chunks: tuple[bytes, ...] | None = None


@dataclass(frozen=True)
class OperationPolicy:
    operation_id: str
    timeout_ms: int
    idempotency: str
    response_mode: str
    max_request_bytes: int


@dataclass(frozen=True)
class PublishedCapability:
    agent_id: str
    capability_code: str
    implementation_code: str
    adapter_code: str
    adapter_version: str
    upstream_ref: str
    credential_ref: str | None
    isolation_mode: str
    status: str
    operations: tuple[OperationPolicy, ...]
    binding_version: int = 1

    def operation(self, operation_id: str) -> OperationPolicy | None:
        return next((item for item in self.operations if item.operation_id == operation_id), None)


@dataclass(frozen=True)
class InvocationSubject:
    tenant_id: str
    user_id: str
    agent_id: str
    session_id: str


@dataclass(frozen=True)
class AdapterRequest:
    operation: OperationPolicy
    subject: InvocationSubject
    conversation_id: str
    request_id: str
    payload: object
    upstream_ref: str
    credential: str | None = None
    actor_token: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class AdapterResponse:
    status: int
    headers: tuple[tuple[bytes, bytes], ...]
    body: bytes
    chunks: tuple[bytes, ...] | None = None

    @classmethod
    def json(cls, status: int, value: object) -> "AdapterResponse":
        return cls(status, ((b"content-type", b"application/json"),),
                   json.dumps(value, separators=(",", ":")).encode())

    @classmethod
    def stream(cls, chunks: tuple[bytes, ...]) -> "AdapterResponse":
        return cls(200, ((b"content-type", b"text/event-stream"), (b"cache-control", b"no-cache")),
                   b"", tuple(chunks))


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[tuple[str, str], object] = {}

    def register(self, code: str, version: str, adapter) -> None:
        key = (code, version)
        if key in self._adapters:
            raise ValueError("adapter already registered")
        self._adapters[key] = adapter

    def resolve(self, code: str, version: str):
        return self._adapters.get((code, version))


class MappingSecretResolver:
    def __init__(self, secrets: dict[str, str]) -> None:
        self._secrets = dict(secrets)

    def resolve(self, reference: str) -> str:
        try: return self._secrets[reference]
        except KeyError as error: raise LookupError("secret reference unavailable") from error


class EnvironmentSecretResolver:
    """Resolves only named environment values or explicitly mounted file aliases."""

    _NAME = re.compile(r"[A-Z][A-Z0-9_]{0,127}")
    _ALIAS = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
    _CONTROL_ALIAS = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}")

    def __init__(self, *, environ, mounted_files: dict[str, Path] | None = None) -> None:
        self._environ = environ
        self._mounted_files = {name: Path(path) for name, path in (mounted_files or {}).items()}

    def resolve(self, reference: str) -> str:
        if reference.startswith("env://"):
            name = reference[6:]
            if not self._NAME.fullmatch(name):
                raise LookupError("secret reference unavailable")
            value = self._environment_value(name)
        elif reference.startswith("secret://"):
            alias = reference[9:]
            if (not self._CONTROL_ALIAS.fullmatch(alias) or ".." in alias
                    or "//" in alias or alias.endswith("/")):
                raise LookupError("secret reference unavailable")
            name = "GENB_SECRET_" + re.sub(r"[^A-Za-z0-9]", "_", alias).upper()
            value = self._environment_value(name)
        elif reference.startswith("file://"):
            alias = reference[7:]
            if not self._ALIAS.fullmatch(alias) or alias not in self._mounted_files:
                raise LookupError("secret reference unavailable")
            try:
                if self._mounted_files[alias].stat().st_size > 16_384:
                    raise LookupError("secret reference unavailable")
                value = self._mounted_files[alias].read_text(encoding="utf-8").rstrip("\r\n")
            except OSError as error:
                raise LookupError("secret reference unavailable") from error
        else:
            raise LookupError("secret reference unavailable")
        if not isinstance(value, str) or not value:
            raise LookupError("secret reference unavailable")
        return value

    def _environment_value(self, name: str) -> str | None:
        value = self._environ.get(name)
        if not value and self._environ.get(name + "_FILE"):
            try:
                path = Path(self._environ[name + "_FILE"])
                if path.stat().st_size > 16_384:
                    raise LookupError("secret reference unavailable")
                value = path.read_text(encoding="utf-8").rstrip("\r\n")
            except OSError as error:
                raise LookupError("secret reference unavailable") from error
        return value


class StaticActorTokenProvider:
    def __init__(self, token: str) -> None: self._token = token
    def issue(self, session, capability_code: str, binding_version: int = 1) -> str: return self._token


class NoActorTokenProvider:
    def issue(self, session, capability_code: str, binding_version: int = 1) -> str | None: return None


class NoSecretResolver:
    def resolve(self, reference: str) -> str: raise LookupError("secret resolver unavailable")


class IdempotencyConflict(Exception): pass


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._values: dict[tuple, tuple[str, AdapterResponse]] = {}
        self._lock = threading.Lock()

    def execute(self, key: tuple, digest: str, invoke) -> AdapterResponse:
        with self._lock:
            existing = self._values.get(key)
            if existing:
                if existing[0] != digest: raise IdempotencyConflict()
                return existing[1]
            response = invoke()
            if 200 <= response.status < 300:
                self._values[key] = (digest, response)
            return response


class CircuitOpen(Exception): pass


class RateLimited(Exception): pass


class InMemoryRateLimiter:
    """Fixed-window adapter keyed by the signed invocation subject and operation."""

    def __init__(self, clock, *, limit: int = 120, window: timedelta = timedelta(minutes=1)) -> None:
        if limit < 1 or window <= timedelta(0):
            raise ValueError("rate limit and window must be positive")
        self.clock, self.limit, self.window = clock, limit, window
        self._events: dict[tuple, deque] = {}
        self._lock = threading.Lock()

    def check(self, key: tuple) -> None:
        now = self.clock()
        cutoff = now - self.window
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                raise RateLimited()
            events.append(now)


class InMemoryCircuitBreaker:
    def __init__(self, clock, *, threshold: int = 3, cooldown: timedelta = timedelta(seconds=30)) -> None:
        self.clock, self.threshold, self.cooldown = clock, threshold, cooldown
        self._states: dict[tuple, tuple[int, object | None]] = {}
        self._lock = threading.Lock()

    def before(self, key: tuple) -> None:
        with self._lock:
            failures, opened_at = self._states.get(key, (0, None))
            if opened_at is None: return
            if self.clock() - opened_at < self.cooldown: raise CircuitOpen()
            self._states[key] = (0, None)

    def success(self, key: tuple) -> None:
        with self._lock: self._states.pop(key, None)

    def failure(self, key: tuple) -> None:
        with self._lock:
            failures, opened_at = self._states.get(key, (0, None))
            failures += 1
            self._states[key] = (failures, self.clock() if failures >= self.threshold else opened_at)


class PublishedCapabilityTable:
    def __init__(self, bindings: list) -> None:
        self.replace(bindings)

    def replace(self, bindings: list) -> None:
        self._bindings = {(item.agent_id, item.capability_code): item for item in bindings}

    def resolve(self, agent_id: str, capability_code: str):
        return self._bindings.get((agent_id, capability_code))

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "PublishedCapabilityTable":
        if not isinstance(snapshot, dict) or snapshot.get("schemaVersion") not in {"1.0", "1.1"}:
            raise ValueError("unsupported data-plane snapshot")
        try:
            implementations = {item["implementationCode"]: item for item in snapshot["implementations"]}
            if len(implementations) != len(snapshot["implementations"]):
                raise ValueError("duplicate implementation code")
            compiled = []
            for binding in snapshot["bindings"]:
                implementation = implementations[binding["implementationCode"]]
                if implementation["capabilityCode"] != binding["capabilityCode"]:
                    raise ValueError("binding capability mismatch")
                operations = tuple(OperationPolicy(
                    item["operationId"], item["timeoutMs"], item["idempotency"],
                    item["responseMode"], item["maxRequestBytes"],
                ) for item in implementation["operations"])
                status = "PUBLISHED" if (
                    binding["status"] == "ACTIVE" and implementation["status"] == "PUBLISHED"
                ) else "DISABLED"
                compiled.append(PublishedCapability(
                    binding["agentId"], binding["capabilityCode"], implementation["implementationCode"],
                    implementation["adapterCode"], implementation["adapterVersion"],
                    implementation["upstreamRef"], implementation["credentialRef"],
                    implementation["isolationMode"], status, operations, binding["bindingVersion"],
                ))
        except (KeyError, TypeError) as error:
            raise ValueError("invalid data-plane snapshot") from error
        return cls(compiled)


class CapabilityInvocationModule:
    """Deep Module for identity, binding, policy, Adapter, Secret and normalized errors."""

    def __init__(self, *, capabilities: PublishedCapabilityTable, adapters: AdapterRegistry,
                 agent_credentials: dict[str, str],
                 identity, sessions, clock, secret_resolver=None, actor_tokens=None, audit_sink=None) -> None:
        self.capabilities, self.adapters = capabilities, adapters
        self.identity, self.sessions, self.clock = identity, sessions, clock
        self.secret_resolver = secret_resolver or NoSecretResolver()
        self.actor_tokens = actor_tokens or NoActorTokenProvider()
        self.audit_sink = audit_sink
        self.idempotency = InMemoryIdempotencyStore()
        self.breaker = InMemoryCircuitBreaker(clock)
        self.rate_limiter = InMemoryRateLimiter(clock)
        self._executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="genb-capability")
        self._credential_hashes = {agent: hashlib.sha256(secret.encode()).digest()
                                   for agent, secret in agent_credentials.items()}

    def invoke(self, capability: str, operation: str, identity_token: str, agent_credential: str | None,
               envelope: dict, idempotency_key: str | None) -> InvocationResult:
        request_id = self._request_id(envelope)
        try:
            claims = self.identity.verify_invocation(identity_token)
        except Exception as error:
            raise InvocationProblem(401, "INVALID_IDENTITY_TOKEN", "Identity token is invalid or expired", request_id) from error
        expected = self._credential_hashes.get(claims["agentId"])
        actual = hashlib.sha256((agent_credential or "").encode()).digest()
        if expected is None or not hmac.compare_digest(expected, actual):
            raise InvocationProblem(401, "INVALID_AGENT_IDENTITY", "Agent machine identity is invalid", request_id)
        session = self.sessions.resolve_subject(session_id=claims["sessionId"], tenant_id=claims["tenantId"],
                                                user_id=claims["userId"], agent_id=claims["agentId"])
        if session is None:
            raise InvocationProblem(401, "INVALID_IDENTITY_TOKEN", "Identity session is revoked or expired", request_id)
        try:
            binding = self.capabilities.resolve(claims["agentId"], capability)
        except RuntimeError as error:
            raise InvocationProblem(503, "CONFIGURATION_UNAVAILABLE", "Published capability configuration is unavailable",
                                    request_id, True) from error
        if binding is None:
            self._audit(claims, capability, request_id, "DENIED")
            raise InvocationProblem(403, "CAPABILITY_NOT_BOUND", "Capability is not bound to this agent", request_id)
        if binding.status != "PUBLISHED":
            self._audit(claims, capability, request_id, "DENIED")
            raise InvocationProblem(503, "IMPLEMENTATION_UNAVAILABLE", "Capability implementation is unavailable", request_id)
        operation_policy = binding.operation(operation)
        if operation_policy is None:
            self._audit(claims, capability, request_id, "DENIED")
            raise InvocationProblem(404, "OPERATION_NOT_FOUND", "Operation is not published for this capability", request_id)
        adapter = self.adapters.resolve(binding.adapter_code, binding.adapter_version)
        if adapter is None:
            raise InvocationProblem(503, "IMPLEMENTATION_UNAVAILABLE", "Compiled Adapter is unavailable", request_id)
        context, payload = self._validate_envelope(envelope, request_id)
        encoded_size = len(json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode())
        if encoded_size > operation_policy.max_request_bytes:
            raise InvocationProblem(413, "REQUEST_TOO_LARGE", "Invocation request exceeds the published limit", request_id)
        if operation_policy.idempotency == "REQUIRED_KEY" and not idempotency_key:
            raise InvocationProblem(400, "IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required", request_id)
        rate_key = (claims["tenantId"], claims["userId"], claims["agentId"], capability, operation)
        try:
            self.rate_limiter.check(rate_key)
        except RateLimited as error:
            raise InvocationProblem(429, "RATE_LIMITED", "Capability invocation rate limit exceeded", request_id, True) from error

        def invoke_adapter():
            credential = self.secret_resolver.resolve(binding.credential_ref) if binding.credential_ref else None
            actor_token = self.actor_tokens.issue(session, capability, binding.binding_version)
            adapter_request = AdapterRequest(
                operation=operation_policy,
                subject=InvocationSubject(claims["tenantId"], claims["userId"], claims["agentId"], claims["sessionId"]),
                conversation_id=context["conversationId"], request_id=context["requestId"], payload=payload,
                upstream_ref=binding.upstream_ref, credential=credential, actor_token=actor_token,
                idempotency_key=idempotency_key,
            )
            breaker_key = (binding.implementation_code, binding.adapter_code, binding.adapter_version)
            attempts = 2 if operation_policy.idempotency == "READ" else 1
            for attempt in range(attempts):
                self.breaker.before(breaker_key)
                future = self._executor.submit(adapter.invoke, adapter_request)
                try:
                    response = future.result(timeout=operation_policy.timeout_ms / 1000)
                except (FutureTimeout, RuntimeError, OSError):
                    self.breaker.failure(breaker_key)
                    if attempt + 1 == attempts:
                        raise
                    continue
                self.breaker.success(breaker_key)
                return response
            raise RuntimeError("adapter invocation attempts exhausted")

        try:
            if operation_policy.idempotency == "REQUIRED_KEY":
                canonical = json.dumps({"conversationId": context["conversationId"], "payload": payload},
                                       sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                digest = hashlib.sha256(canonical.encode()).hexdigest()
                key = (claims["tenantId"], claims["userId"], claims["agentId"], capability, operation, idempotency_key)
                response = self.idempotency.execute(key, digest, invoke_adapter)
            else:
                response = invoke_adapter()
        except IdempotencyConflict as error:
            self._audit(claims, capability, request_id, "DENIED")
            raise InvocationProblem(409, "IDEMPOTENCY_CONFLICT", "Idempotency-Key was used with another payload", request_id) from error
        except FutureTimeout as error:
            self._audit(claims, capability, request_id, "ERROR")
            raise InvocationProblem(504, "UPSTREAM_TIMEOUT", "Capability upstream timed out", request_id, True) from error
        except CircuitOpen as error:
            self._audit(claims, capability, request_id, "ERROR")
            raise InvocationProblem(503, "CIRCUIT_OPEN", "Capability upstream circuit is open", request_id, True) from error
        except (LookupError, RuntimeError, OSError) as error:
            _LOG.warning(
                "capability invocation failed capability=%s operation=%s error_type=%s error=%s",
                capability, operation, type(error).__name__, str(error),
            )
            self._audit(claims, capability, request_id, "ERROR")
            raise InvocationProblem(503, "UPSTREAM_UNAVAILABLE", "Capability upstream is unavailable", request_id) from error
        if operation_policy.response_mode == "SSE" and response.chunks is None:
            raise InvocationProblem(502, "INVALID_UPSTREAM_RESPONSE", "Streaming response was not provided", request_id)
        if operation_policy.response_mode != "SSE" and response.chunks is not None:
            raise InvocationProblem(502, "INVALID_UPSTREAM_RESPONSE", "Unexpected streaming response", request_id)
        self._audit(claims, capability, request_id, "SUCCESS")
        return InvocationResult(response.status, response.headers, response.body, response.chunks)

    def _audit(self, claims: dict, capability: str, request_id: str | None, outcome: str) -> None:
        if self.audit_sink is None:
            return
        try:
            from .audit import AuditEvent
            self.audit_sink.append(AuditEvent(
                event_id=secrets.token_hex(16), occurred_at=self.clock(),
                request_id=(request_id or "unknown")[:128], event_type="CAPABILITY_INVOKED", outcome=outcome,
                tenant_id=claims["tenantId"], user_id=claims["userId"], agent_id=claims["agentId"],
                capability_code=capability,
            ))
        except Exception:
            # Audit backpressure is observable on the sink but never leaks or rewrites the business response.
            return

    @staticmethod
    def _request_id(envelope: dict) -> str | None:
        context = envelope.get("context") if isinstance(envelope, dict) else None
        return context.get("requestId") if isinstance(context, dict) and isinstance(context.get("requestId"), str) else None

    @staticmethod
    def _validate_envelope(envelope: dict, request_id: str | None):
        if set(envelope) != {"schemaVersion", "context", "payload"} or envelope.get("schemaVersion") != "1.0":
            raise InvocationProblem(400, "INVALID_REQUEST", "Invocation envelope is invalid", request_id)
        context = envelope.get("context")
        if not isinstance(context, dict) or set(context) != {"requestId", "conversationId"}:
            raise InvocationProblem(400, "INVALID_REQUEST", "Invocation context is invalid", request_id)
        if not all(isinstance(context.get(key), str) and context[key] for key in ("requestId", "conversationId")):
            raise InvocationProblem(400, "INVALID_REQUEST", "Invocation context is invalid", request_id)
        return context, envelope["payload"]
