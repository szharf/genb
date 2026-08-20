from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
import json
import secrets
import re
from typing import Callable
from urllib.parse import parse_qs, urlencode

from .access import AccessDecisionModule, AccessDenied
from .identity import IdentityTokens
from .routing import PublishedRouteTable, validate_agent_path
from .sessions import InMemorySessionStore, LoginStateStore


@dataclass(frozen=True)
class GatewaySettings:
    public_origin: str
    portal_authorize_url: str
    callback_url: str
    nginx_token: str
    cookie_secure: bool = True
    session_ttl: timedelta = timedelta(hours=8)
    identity_ttl: timedelta = timedelta(seconds=60)
    control_invalidation_token: str | None = None


class GatewayApp:
    def __init__(self, *, settings: GatewaySettings, control_plane, routes: PublishedRouteTable,
                 clock: Callable[[], datetime], session_store=None, identity_tokens=None, capability_invocation=None,
                 runtime_state=None, actor_token_cache=None) -> None:
        self.settings, self.control_plane, self.routes, self.clock = settings, control_plane, routes, clock
        self.sessions = session_store or InMemorySessionStore(clock)
        self.states = LoginStateStore(clock)
        self.identity = identity_tokens or IdentityTokens(clock, settings.identity_ttl)
        self.access = AccessDecisionModule(self.sessions, routes, self.identity)
        self.capability_invocation = capability_invocation
        self.runtime_state, self.actor_token_cache = runtime_state, actor_token_cache

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return
        method, path = scope["method"], scope["path"]
        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        query = parse_qs(scope.get("query_string", b"").decode(), keep_blank_values=True)
        try:
            if method == "GET" and path == "/health/live":
                return await self._json(200, {"status":"UP"}, send)
            if method == "GET" and path == "/health/ready":
                return await self._ready(send)
            if method == "GET" and path == "/agents/_auth/login":
                return await self._login(query, send)
            if method == "GET" and path == "/agents/_auth/callback":
                return await self._callback(query, send)
            if method == "POST" and path == "/agents/_auth/logout":
                return await self._logout(headers, send)
            if method == "GET" and path == "/internal/agent-access/authorize":
                return await self._authorize(query, headers, send)
            if method == "GET" and path == "/.well-known/genb-gateway-jwks.json":
                return await self._json(200, self.identity.jwks(), send)
            if method == "POST" and path == "/internal/cache/invalidate":
                return await self._invalidate_cache(headers, receive, send)
            capability_match = re.fullmatch(
                r"/component-api/v1/capabilities/([A-Z][A-Z0-9_]*)/operations/([A-Za-z0-9][A-Za-z0-9._-]*):invoke",
                path,
            )
            if method == "POST" and capability_match and self.capability_invocation:
                return await self._invoke_capability(capability_match.group(1), capability_match.group(2), headers, receive, send)
            return await self._problem(404, "NOT_FOUND", "Interface not found", send)
        except (KeyError, ValueError):
            return await self._problem(400, "INVALID_REQUEST", "Request validation failed", send)

    async def _ready(self, send) -> None:
        if self.runtime_state is not None:
            try:
                state = self.runtime_state.refresh()
                self.runtime_state.current(risk="HIGH")
            except RuntimeError:
                return await self._json(503, {"status":"DOWN", "code":"CONFIGURATION_UNAVAILABLE"}, send)
            return await self._json(200, {"status":"UP", "configVersion":state.config_version}, send)
        await self._json(200, {"status":"UP"}, send)

    async def _login(self, query, send) -> None:
        agent_id = self._one(query, "agentId")
        return_path = self._one(query, "returnPath")
        if self.routes.resolve(agent_id) is None or not validate_agent_path(agent_id, return_path):
            return await self._problem(400, "INVALID_RETURN_PATH", "Invalid agent or return path", send)
        state = self.states.create(agent_id, return_path)
        location = self.settings.portal_authorize_url + "?" + urlencode({
            "agentId": agent_id, "callbackUrl": self.settings.callback_url, "state": state,
        })
        await self._respond(303, b"", send, [(b"location", location.encode())])

    async def _callback(self, query, send) -> None:
        code, state = self._one(query, "code"), self._one(query, "state")
        pending = self.states.consume(state)
        if pending is None:
            return await self._problem(401, "INVALID_LOGIN_STATE", "Login state is invalid or expired", send)
        session_id = secrets.token_urlsafe(24)
        try:
            subject = self.control_plane.exchange(code=code, state=state, agent_id=pending.agent_id,
                                                  callback_url=self.settings.callback_url, session_id=session_id)
        except PermissionError:
            return await self._problem(401, "AUTHORIZATION_CODE_INVALID", "Authorization code rejected", send)
        if subject.agent_id != pending.agent_id or subject.session_id != session_id:
            return await self._problem(401, "IDENTITY_EXCHANGE_MISMATCH", "Identity exchange mismatch", send)
        token = self.sessions.create(
            ttl=self.settings.session_ttl, session_id=session_id, tenant_id=subject.tenant_id,
            user_id=str(subject.user_id), username=subject.username, agent_id=subject.agent_id,
            session_grant=subject.session_grant,
        )
        cookie = self._cookie(token)
        await self._respond(303, b"", send, [(b"location", pending.return_path.encode()), (b"set-cookie", cookie.encode())])

    async def _logout(self, headers, send) -> None:
        if headers.get("origin") != self.settings.public_origin:
            return await self._problem(403, "INVALID_ORIGIN", "Same-origin request required", send)
        session = self.sessions.revoke(self._session_cookie(headers))
        if session:
            self.control_plane.revoke(session.agent_id, session.session_grant)
        expired = "genb_gateway_session=; Path=/agents; HttpOnly; SameSite=Lax; Max-Age=0"
        if self.settings.cookie_secure:
            expired += "; Secure"
        await self._respond(204, b"", send, [(b"set-cookie", expired.encode())])

    async def _authorize(self, query, headers, send) -> None:
        if not secrets.compare_digest(headers.get("x-genb-nginx-identity", ""), self.settings.nginx_token):
            return await self._problem(401, "INVALID_PROXY_IDENTITY", "Trusted proxy identity required", send)
        agent_id, request_path = self._one(query, "agentId"), self._one(query, "requestPath")
        try:
            decision = self.access.authorize(agent_id, self._session_cookie(headers), request_path)
        except AccessDenied as error:
            return await self._problem(error.status, error.code, error.detail, send)
        await self._respond(204, b"", send, list(decision.headers))

    async def _invoke_capability(self, capability, operation, headers, receive, send) -> None:
        from .capabilities import InvocationProblem
        try:
            envelope = await self._read_json(receive)
            authorization = headers.get("authorization", "")
            if not authorization.startswith("Bearer "):
                raise InvocationProblem(401, "INVALID_IDENTITY_TOKEN", "Identity token required")
            result = self.capability_invocation.invoke(
                capability, operation, authorization[7:], headers.get("x-genb-agent-credential"),
                envelope, headers.get("idempotency-key"),
            )
            if result.chunks is not None:
                await self._respond_stream(result.status, result.chunks, send, list(result.headers))
            else:
                await self._respond(result.status, result.body, send, list(result.headers))
        except InvocationProblem as error:
            await self._problem(error.status, error.code, error.detail, send, request_id=error.request_id,
                                retriable=error.retriable)

    async def _invalidate_cache(self, headers, receive, send) -> None:
        expected = self.settings.control_invalidation_token or ""
        authorization = headers.get("authorization", "")
        if not expected or not authorization.startswith("Bearer ") or not secrets.compare_digest(authorization[7:], expected):
            return await self._problem(401, "INVALID_AGENT_IDENTITY", "GenB machine identity required", send)
        value = await self._read_json(receive)
        if value.get("schemaVersion") != "1.0" or not isinstance(value.get("configVersion"), int):
            return await self._problem(400, "INVALID_REQUEST", "Invalid cache invalidation event", send)
        scope = value.get("scope")
        try:
            if scope == "CONFIG" and set(value) == {"schemaVersion", "scope", "configVersion"}:
                if self.runtime_state is None:
                    raise RuntimeError("runtime state unavailable")
                current = self.runtime_state.invalidate()
                if current.config_version < value["configVersion"]:
                    raise RuntimeError("requested config version unavailable")
                if self.actor_token_cache is not None:
                    self.actor_token_cache.invalidate()
            elif scope == "CAPABILITY" and set(value) == {
                    "schemaVersion", "scope", "configVersion", "agentId", "capabilityCode"}:
                if self.runtime_state is None:
                    raise RuntimeError("runtime state unavailable")
                current = self.runtime_state.invalidate()
                if current.config_version < value["configVersion"]:
                    raise RuntimeError("requested config version unavailable")
                if self.actor_token_cache is not None:
                    self.actor_token_cache.invalidate(agent_id=value["agentId"], capability_code=value["capabilityCode"])
            elif scope == "SESSION" and set(value) == {
                    "schemaVersion", "scope", "configVersion", "tenantId", "userId", "agentId", "sessionId"}:
                self.sessions.revoke_subject(
                    session_id=value["sessionId"], tenant_id=value["tenantId"],
                    user_id=value["userId"], agent_id=value["agentId"],
                )
                if self.actor_token_cache is not None:
                    self.actor_token_cache.invalidate(agent_id=value["agentId"], session_id=value["sessionId"])
            elif scope == "USER_AGENT" and set(value) == {
                    "schemaVersion", "scope", "configVersion", "tenantId", "userId", "agentId"}:
                self.sessions.revoke_access(
                    tenant_id=value["tenantId"], user_id=value["userId"], agent_id=value["agentId"],
                )
                if self.actor_token_cache is not None:
                    self.actor_token_cache.invalidate(agent_id=value["agentId"])
            elif scope == "AGENT" and set(value) == {
                    "schemaVersion", "scope", "configVersion", "agentId"}:
                self.sessions.revoke_agent(agent_id=value["agentId"])
                if self.actor_token_cache is not None:
                    self.actor_token_cache.invalidate(agent_id=value["agentId"])
            else:
                return await self._problem(400, "INVALID_REQUEST", "Invalid cache invalidation scope", send)
        except (ConnectionError, OSError, RuntimeError):
            return await self._problem(503, "CONFIGURATION_UNAVAILABLE", "Cache invalidation could not be applied", send,
                                       retriable=True)
        await self._json(202, {"schemaVersion":"1.0", "appliedConfigVersion":value["configVersion"]}, send)

    @staticmethod
    async def _read_json(receive) -> dict:
        chunks = []
        while True:
            message = await receive()
            if message["type"] != "http.request":
                raise ValueError("request body unavailable")
            chunks.append(message.get("body", b""))
            if sum(map(len, chunks)) > 1_048_576:
                raise ValueError("request body too large")
            if not message.get("more_body", False): break
        value = json.loads(b"".join(chunks))
        if not isinstance(value, dict): raise ValueError("JSON object required")
        return value

    def _cookie(self, value: str) -> str:
        cookie = f"genb_gateway_session={value}; Path=/agents; HttpOnly; SameSite=Lax; Max-Age={int(self.settings.session_ttl.total_seconds())}"
        return cookie + ("; Secure" if self.settings.cookie_secure else "")

    @staticmethod
    def _session_cookie(headers) -> str | None:
        cookie = SimpleCookie(); cookie.load(headers.get("cookie", ""))
        return cookie["genb_gateway_session"].value if "genb_gateway_session" in cookie else None

    @staticmethod
    def _one(query, name: str) -> str:
        values = query.get(name)
        if not values or len(values) != 1 or not values[0]:
            raise ValueError(name)
        return values[0]

    async def _json(self, status, value, send) -> None:
        await self._respond(status, json.dumps(value, separators=(",", ":")).encode(), send,
                            [(b"content-type", b"application/json")])

    async def _problem(self, status, code, detail, send, *, request_id=None, retriable=False) -> None:
        value = {"type": "about:blank", "title": code.replace("_", " ").title(), "status": status,
                 "detail": detail, "code": code, "requestId": request_id or secrets.token_hex(8), "retriable": retriable}
        await self._respond(status, json.dumps(value, separators=(",", ":")).encode(), send,
                            [(b"content-type", b"application/problem+json")])

    @staticmethod
    async def _respond(status, body, send, headers=None) -> None:
        response_headers = list(headers or [])
        response_headers.append((b"content-length", str(len(body)).encode()))
        await send({"type": "http.response.start", "status": status, "headers": response_headers})
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    async def _respond_stream(status, chunks, send, headers=None) -> None:
        await send({"type":"http.response.start", "status":status, "headers":list(headers or [])})
        for index, chunk in enumerate(chunks):
            await send({"type":"http.response.body", "body":chunk, "more_body":index < len(chunks) - 1})


def create_app(*, settings: GatewaySettings, control_plane, routes: PublishedRouteTable,
               clock: Callable[[], datetime] | None = None, session_store=None, identity_tokens=None,
               capability_invocation=None, runtime_state=None, actor_token_cache=None) -> GatewayApp:
    return GatewayApp(settings=settings, control_plane=control_plane, routes=routes,
                      clock=clock or (lambda: datetime.now(timezone.utc)), session_store=session_store,
                      identity_tokens=identity_tokens, capability_invocation=capability_invocation,
                      runtime_state=runtime_state, actor_token_cache=actor_token_cache)
