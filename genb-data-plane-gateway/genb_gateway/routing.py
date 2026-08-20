from __future__ import annotations

from dataclasses import dataclass, replace
import ipaddress
import re
from urllib.parse import unquote, urlsplit


AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class PublishedAgentRoute:
    agent_id: str
    upstream: str
    identity_mode: str
    allowed_users: frozenset[str]


class PublishedRouteTable:
    def __init__(self, *, routes: list[PublishedAgentRoute], allowed_upstreams: frozenset[tuple[str, int]]) -> None:
        self._allowed_upstreams = allowed_upstreams
        self._routes: dict[str, PublishedAgentRoute] = {}
        for route in routes:
            self._validate(route)
            self._routes[route.agent_id] = route

    def resolve(self, agent_id: str) -> PublishedAgentRoute | None:
        return self._routes.get(agent_id)

    def revoke_user(self, agent_id: str, user_id: str) -> None:
        route = self._routes.get(agent_id)
        if route:
            self._routes[agent_id] = replace(route, allowed_users=route.allowed_users - {user_id})

    def _validate(self, route: PublishedAgentRoute) -> None:
        if not AGENT_ID.fullmatch(route.agent_id) or route.identity_mode not in {"NONE", "SIGNED_TOKEN"}:
            raise ValueError("invalid published agent route")
        parsed = urlsplit(route.upstream)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("invalid upstream")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("upstream must be an origin")
        if (parsed.hostname, port) not in self._allowed_upstreams:
            raise ValueError("upstream is not in the published allowlist")
        try:
            address = ipaddress.ip_address(parsed.hostname)
            if address.is_unspecified or address.is_multicast or address.is_link_local:
                raise ValueError("unsafe upstream network")
        except ValueError as error:
            if str(error) == "unsafe upstream network":
                raise


def validate_agent_path(agent_id: str, path: str) -> bool:
    if not AGENT_ID.fullmatch(agent_id) or not path.startswith("/") or "\\" in path:
        return False
    once = unquote(path)
    if once != path or "%" in once:
        return False
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        return False
    expected = f"/agents/{agent_id}"
    if parsed.path != expected and not parsed.path.startswith(expected + "/"):
        return False
    return all(segment not in {".", ".."} for segment in parsed.path.split("/"))


def validate_request_path(path: str) -> bool:
    if not path.startswith("/") or "\\" in path:
        return False
    once = unquote(path)
    return once == path and "%" not in once and all(part not in {".", ".."} for part in once.split("/"))
