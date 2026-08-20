from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from .adapters import build_default_adapter_registry
from .app import GatewaySettings, create_app
from .audit import AuditBuffer, RedisAuditStore
from .capabilities import CapabilityInvocationModule, EnvironmentSecretResolver
from .control import ControlPlaneActorTokenProvider, HttpControlPlane
from .identity import IdentityTokens
from .runtime_state import ControlSnapshotModule, RedisSnapshotStore
from .sessions import L1SessionStore, RedisSessionStore, RespRedisClient
from .tokens import CachingActorTokenProvider


_HOST_PORT = re.compile(r"([A-Za-z0-9][A-Za-z0-9.-]{0,252}):(\d{1,5})")
_AGENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def _required(environment, name: str) -> str:
    value = environment.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"required environment value is missing: {name}")
    return value.strip()


def _required_secret(environment, name: str) -> str:
    direct, file_name = environment.get(name), environment.get(name + "_FILE")
    if direct and file_name:
        raise ValueError(f"set only one of {name} and {name}_FILE")
    if file_name:
        path = Path(file_name)
        try:
            if path.stat().st_size > 16_384:
                raise ValueError(f"secret file is too large: {name}_FILE")
            direct = path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise ValueError(f"secret file is unreadable: {name}_FILE") from error
    if not isinstance(direct, str) or not direct.strip():
        raise ValueError(f"required secret is missing: {name} or {name}_FILE")
    return direct.strip()


def _optional_secret(environment, name: str) -> str | None:
    if not environment.get(name) and not environment.get(name + "_FILE"):
        return None
    return _required_secret(environment, name)


def _upstreams(value: str) -> frozenset[tuple[str, int]]:
    parsed = set()
    for item in value.split(","):
        match = _HOST_PORT.fullmatch(item.strip())
        if match is None or not 1 <= int(match.group(2)) <= 65535:
            raise ValueError("GENB_ALLOWED_UPSTREAMS must be a comma-separated host:port allowlist")
        parsed.add((match.group(1), int(match.group(2))))
    if not parsed:
        raise ValueError("GENB_ALLOWED_UPSTREAMS cannot be empty")
    return frozenset(parsed)


def _agent_credentials(value: str) -> dict[str, str]:
    result = {}
    for item in value.split(","):
        agent_id, separator, credential = item.strip().partition("=")
        if not separator or not _AGENT.fullmatch(agent_id) or not credential:
            raise ValueError("GENB_AGENT_CREDENTIALS must contain agentId=credential entries")
        if agent_id in result:
            raise ValueError("GENB_AGENT_CREDENTIALS contains a duplicate agent")
        result[agent_id] = credential
    if not result:
        raise ValueError("GENB_AGENT_CREDENTIALS cannot be empty")
    return result


def build_gateway(environment, *, clock=None, control_plane=None, redis=None):
    """Builds the complete single-process runtime from a closed environment interface."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    control_url = _required(environment, "GENB_CONTROL_URL")
    machine_token = _required_secret(environment, "GENB_GATEWAY_MACHINE_TOKEN")
    public_origin = _required(environment, "GENB_PUBLIC_ORIGIN")
    portal_url = _required(environment, "GENB_PORTAL_AUTHORIZE_URL")
    callback_url = _required(environment, "GENB_GATEWAY_CALLBACK_URL")
    nginx_token = _required_secret(environment, "GENB_NGINX_TOKEN")
    invalidation_token = _required_secret(environment, "GENB_INVALIDATION_TOKEN")
    redis_host = _required(environment, "GENB_REDIS_HOST")
    allowed_upstreams = _upstreams(_required(environment, "GENB_ALLOWED_UPSTREAMS"))
    agent_credentials = _agent_credentials(_required_secret(environment, "GENB_AGENT_CREDENTIALS"))

    control_plane = control_plane or HttpControlPlane(control_url, machine_token)
    redis = redis or RespRedisClient(
        redis_host, int(environment.get("GENB_REDIS_PORT", "6379")),
        timeout=float(environment.get("GENB_REDIS_TIMEOUT_SECONDS", "1.0")),
        password=_optional_secret(environment, "GENB_REDIS_PASSWORD"),
    )
    runtime_state = ControlSnapshotModule(
        source=control_plane, store=RedisSnapshotStore(redis), clock=clock, allowed_upstreams=allowed_upstreams,
    )
    runtime_state.start()
    sessions = L1SessionStore(RedisSessionStore(redis, clock), clock)
    identity = IdentityTokens(clock, timedelta(seconds=60))
    actor_tokens = CachingActorTokenProvider(ControlPlaneActorTokenProvider(control_plane), clock)
    audits = AuditBuffer(RedisAuditStore(
        redis, max_length=int(environment.get("GENB_AUDIT_MAX_LENGTH", "10000")),
    ), control_plane)
    capabilities = CapabilityInvocationModule(
        capabilities=runtime_state, adapters=build_default_adapter_registry(),
        agent_credentials=agent_credentials, identity=identity, sessions=sessions, clock=clock,
        secret_resolver=EnvironmentSecretResolver(environ=environment), actor_tokens=actor_tokens,
        audit_sink=audits,
    )
    settings = GatewaySettings(
        public_origin=public_origin, portal_authorize_url=portal_url, callback_url=callback_url,
        nginx_token=nginx_token, cookie_secure=public_origin.startswith("https://"),
        control_invalidation_token=invalidation_token,
    )
    app = create_app(
        settings=settings, control_plane=control_plane, routes=runtime_state, clock=clock,
        session_store=sessions, identity_tokens=identity, capability_invocation=capabilities,
        runtime_state=runtime_state, actor_token_cache=actor_tokens,
    )
    app.audit_buffer = audits
    return app
