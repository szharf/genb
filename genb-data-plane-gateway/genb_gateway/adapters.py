from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
import re
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .capabilities import AdapterRegistry, AdapterResponse


_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    chunks: tuple[bytes, ...] | None = None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None


class UrllibHttpTransport:
    def __init__(self) -> None: self._opener = build_opener(_NoRedirect)

    def send(self, request: HttpRequest, timeout_ms: int) -> HttpResponse:
        outbound = Request(request.url, method=request.method, headers=request.headers, data=request.body)
        try:
            with self._opener.open(outbound, timeout=timeout_ms / 1000) as response:
                content_type = response.headers.get("Content-Type", "")
                if content_type.split(";", 1)[0].lower() == "text/event-stream":
                    chunks = tuple(iter(lambda: response.read(4096), b""))
                    return HttpResponse(response.status, dict(response.headers.items()), b"", chunks)
                return HttpResponse(response.status, dict(response.headers.items()), response.read())
        except HTTPError as error:
            return HttpResponse(error.code, dict(error.headers.items()), error.read())
        except URLError as error:
            raise ConnectionError("upstream request failed") from error


class JsonOperationAdapter:
    operations: dict[str, tuple[str, str]] = {}

    def __init__(self, transport) -> None: self.transport = transport

    def invoke(self, request) -> AdapterResponse:
        try: method, path = self.operations[request.operation.operation_id]
        except KeyError as error: raise LookupError("adapter operation unavailable") from error
        origin = self._origin(request.upstream_ref)
        headers = {
            "Content-Type": "application/json", "Accept": "application/json",
            "X-Request-Id": request.request_id,
        }
        if request.credential: headers["Authorization"] = "Bearer " + request.credential
        if request.actor_token: headers["X-GenB-Actor-Token"] = request.actor_token
        if request.idempotency_key: headers["Idempotency-Key"] = request.idempotency_key
        outbound = HttpRequest(method, origin + path, headers,
                               json.dumps(request.payload, separators=(",", ":"), ensure_ascii=False).encode())
        response = self.transport.send(outbound, request.operation.timeout_ms)
        if response.status < 200 or response.status >= 300:
            _LOG.warning(
                "capability upstream rejected request adapter=%s operation=%s status=%s",
                type(self).__name__, request.operation.operation_id, response.status,
            )
            raise RuntimeError("upstream returned an error")
        content_type = response.headers.get("content-type", response.headers.get("Content-Type", "application/json"))
        return AdapterResponse(response.status, ((b"content-type", content_type.split(";", 1)[0].encode()),),
                               response.body, response.chunks)

    @staticmethod
    def _origin(value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise LookupError("invalid published upstream")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise LookupError("published upstream must be an origin")
        return value.rstrip("/")


class ShortTermMemoryAdapter(JsonOperationAdapter):
    operations = {
        "commitShortTermTurn": ("POST", "/api/v1/short-term-memory/turns:commit"),
        "prepareShortTermContext": ("POST", "/api/v1/short-term-memory/context:prepare"),
    }


class LongTermMemoryAdapter(JsonOperationAdapter):
    operations = {
        "createConversationMemoryExtraction": ("POST", "/api/v1/long-term-memory/extractions"),
        "searchLongTermMemories": ("POST", "/api/v1/long-term-memory/memories:search"),
    }

    _IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")

    def invoke(self, request) -> AdapterResponse:
        if request.operation.operation_id != "getLongTermExtraction":
            return super().invoke(request)
        extraction_id = request.payload.get("extractionId") if isinstance(request.payload, dict) else None
        if not isinstance(extraction_id, str) or not self._IDENTIFIER.fullmatch(extraction_id):
            raise LookupError("invalid extraction identifier")
        headers = {"Accept":"application/json", "X-Request-Id":request.request_id}
        if request.credential: headers["Authorization"] = "Bearer " + request.credential
        if request.actor_token: headers["X-GenB-Actor-Token"] = request.actor_token
        response = self.transport.send(HttpRequest(
            "GET", self._origin(request.upstream_ref) + "/api/v1/long-term-memory/extractions/" + extraction_id,
            headers, b"",
        ), request.operation.timeout_ms)
        if response.status < 200 or response.status >= 300:
            raise RuntimeError("upstream returned an error")
        return AdapterResponse(response.status, ((b"content-type", b"application/json"),), response.body)


class PlanningReasoningAdapter(JsonOperationAdapter):
    operations = {
        "analyzeRequirement": ("POST", "/api/v1/planning-reasoning/requirements:analyze"),
        "converseRequirement": ("POST", "/api/v1/planning-reasoning/requirements:converse"),
        "generateSkill": ("POST", "/api/v1/planning-reasoning/skills:generate"),
        "validateSkill": ("POST", "/api/v1/planning-reasoning/skills:validate"),
    }


class RuntimeInferenceAdapter(JsonOperationAdapter):
    operations = {"completeChat": ("POST", "/api/v1/runtime-system/inference")}


class HeterogeneousFakeAdapter(JsonOperationAdapter):
    def invoke(self, request) -> AdapterResponse:
        if request.operation.operation_id != "summarize" or not request.credential:
            raise LookupError("heterogeneous operation unavailable")
        subject = hashlib.sha256(
            f"{request.subject.tenant_id}\0{request.subject.agent_id}\0{request.subject.user_id}".encode()
        ).hexdigest()
        body = {
            "command": "MAKE_BRIEF", "subjectKey": "sha256:" + subject,
            "arguments": {"sourceText": request.payload.get("text") if isinstance(request.payload, dict) else None},
        }
        response = self.transport.send(HttpRequest(
            "POST", self._origin(request.upstream_ref) + "/v7/execute",
            {"Content-Type":"application/x-vendor+json", "Accept":"application/x-vendor+json",
             "X-Vendor-Key":request.credential, "X-Trace-Ref":request.request_id},
            json.dumps(body, separators=(",", ":")).encode(),
        ), request.operation.timeout_ms)
        if response.status < 200 or response.status >= 300:
            raise RuntimeError("heterogeneous upstream returned an error")
        try:
            value = json.loads(response.body)
            summary = value["output"]["brief"]
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise RuntimeError("heterogeneous upstream response is invalid") from error
        return AdapterResponse.json(200, {"summary": summary})


def build_default_adapter_registry(transport=None) -> AdapterRegistry:
    transport = transport or UrllibHttpTransport()
    registry = AdapterRegistry()
    registry.register("SHORT_TERM_MEMORY_HTTP", "1.0.0", ShortTermMemoryAdapter(transport))
    registry.register("LONG_TERM_MEMORY_HTTP", "1.0.0", LongTermMemoryAdapter(transport))
    registry.register("PLANNING_REASONING_HTTP", "1.0.0", PlanningReasoningAdapter(transport))
    registry.register("RUNTIME_INFERENCE_HTTP", "1.0.0", RuntimeInferenceAdapter(transport))
    registry.register("HETEROGENEOUS_FAKE", "1.0.0", HeterogeneousFakeAdapter(transport))
    return registry
