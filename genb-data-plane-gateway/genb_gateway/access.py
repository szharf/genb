from __future__ import annotations

from dataclasses import dataclass

from .routing import validate_request_path


@dataclass(frozen=True)
class AccessDenied(Exception):
    status: int
    code: str
    detail: str


@dataclass(frozen=True)
class AccessDecision:
    upstream: str
    headers: tuple[tuple[bytes, bytes], ...]


class AccessDecisionModule:
    """Owns session, permission, route and identity decisions; never proxies agent bytes."""

    def __init__(self, sessions, routes, identity) -> None:
        self.sessions, self.routes, self.identity = sessions, routes, identity

    def authorize(self, agent_id: str, session_cookie: str | None, request_path: str) -> AccessDecision:
        if not validate_request_path(request_path):
            raise AccessDenied(400, "INVALID_AGENT_PATH", "Invalid upstream request path")
        session = self.sessions.resolve(session_cookie)
        if session is None or session.agent_id != agent_id:
            raise AccessDenied(401, "INVALID_GATEWAY_SESSION", "Gateway session is invalid or expired")
        try:
            route = self.routes.resolve(agent_id)
        except RuntimeError as error:
            raise AccessDenied(503, "CONFIGURATION_UNAVAILABLE", "Published route configuration is unavailable") from error
        if route is None or ("*" not in route.allowed_users and session.user_id not in route.allowed_users):
            raise AccessDenied(403, "AGENT_ACCESS_DENIED", "Agent access denied")
        headers = [
            (b"x-genb-upstream", route.upstream.encode()),
            (b"x-genb-tenant-id", session.tenant_id.encode()),
            (b"x-genb-user-id", session.user_id.encode()),
            (b"x-genb-agent-id", session.agent_id.encode()),
            (b"x-genb-session-id", session.session_id.encode()),
        ]
        if route.identity_mode == "SIGNED_TOKEN":
            headers.append((b"x-genb-identity-token", self.identity.issue(session).encode()))
        return AccessDecision(route.upstream, tuple(headers))
