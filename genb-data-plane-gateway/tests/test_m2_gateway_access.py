from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit
import unittest

from genb_gateway.app import GatewaySettings, create_app
from genb_gateway.control import FakeControlPlane
from genb_gateway.routing import PublishedAgentRoute, PublishedRouteTable


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 13, 8, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


class AsgiClient:
    def __init__(self, app) -> None:
        self.app = app

    def request(self, method: str, target: str, *, headers: dict[str, str] | None = None, body: bytes = b""):
        split = urlsplit(target)
        sent = []
        received = False

        async def receive():
            nonlocal received
            if received:
                return {"type": "http.disconnect"}
            received = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": method, "scheme": "http", "path": split.path,
            "raw_path": split.path.encode("ascii"), "query_string": split.query.encode("ascii"),
            "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()],
            "server": ("gateway.local", 80), "client": ("127.0.0.1", 12345),
        }
        asyncio.run(self.app(scope, receive, send))
        start = next(message for message in sent if message["type"] == "http.response.start")
        response_headers = {key.decode().lower(): value.decode() for key, value in start["headers"]}
        response_body = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
        return start["status"], response_headers, response_body


class M2GatewayAccessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.control = FakeControlPlane()
        self.control.add_code(
            code="a" * 40, state=None, agent_id="agent-a", tenant_id="tenant-1",
            user_id="user-a", username="alice", session_grant="g" * 40,
        )
        routes = PublishedRouteTable(
            routes=[
                PublishedAgentRoute("agent-a", "http://127.0.0.1:19001", "SIGNED_TOKEN", frozenset({"user-a", "user-b"})),
                PublishedAgentRoute("agent-b", "http://127.0.0.1:19002", "NONE", frozenset({"user-b"})),
            ],
            allowed_upstreams=frozenset({("127.0.0.1", 19001), ("127.0.0.1", 19002)}),
        )
        settings = GatewaySettings(
            public_origin="http://gateway.local", portal_authorize_url="http://portal.local/agent-authorize",
            callback_url="http://gateway.local/agents/_auth/callback", nginx_token="nginx-only",
            cookie_secure=False, session_ttl=timedelta(hours=8), identity_ttl=timedelta(seconds=60),
        )
        self.app = create_app(settings=settings, control_plane=self.control, routes=routes, clock=self.clock)
        self.client = AsgiClient(self.app)

    def login(self, agent_id: str = "agent-a", return_path: str = "/agents/agent-a/chat") -> str:
        status, headers, _ = self.client.request("GET", f"/agents/_auth/login?agentId={agent_id}&returnPath={return_path}")
        self.assertEqual(303, status)
        state = parse_qs(urlsplit(headers["location"]).query)["state"][0]
        self.control.bind_state("a" * 40, state)
        status, headers, _ = self.client.request("GET", f"/agents/_auth/callback?code={'a' * 40}&state={state}")
        self.assertEqual(303, status)
        self.assertEqual(return_path, headers["location"])
        cookie = SimpleCookie(); cookie.load(headers["set-cookie"])
        morsel = cookie["genb_gateway_session"]
        self.assertTrue(morsel["httponly"])
        self.assertEqual("Lax", morsel["samesite"])
        self.assertEqual("/agents", morsel["path"])
        self.assertNotIn("user-a", morsel.value)
        self.assertNotIn("g" * 40, morsel.value)
        return morsel.value

    def authorize(self, cookie: str, agent_id: str = "agent-a", extra: dict[str, str] | None = None):
        headers = {"x-genb-nginx-identity": "nginx-only", "cookie": f"genb_gateway_session={cookie}"}
        headers.update(extra or {})
        return self.client.request("GET", f"/internal/agent-access/authorize?agentId={agent_id}&requestPath=%2Fchat", headers=headers)

    def test_login_callback_cookie_authorize_and_jwks(self) -> None:
        cookie = self.login()
        status, headers, body = self.authorize(cookie)
        self.assertEqual(204, status, body)
        self.assertEqual("http://127.0.0.1:19001", headers["x-genb-upstream"])
        token = headers["x-genb-identity-token"]
        claims = self.app.identity.verify(token, audience="agent-a")
        self.assertEqual(("tenant-1", "user-a", "agent-a"), (claims["tenantId"], claims["userId"], claims["agentId"]))
        self.assertLessEqual(claims["exp"] - claims["iat"], 60)
        jwks_status, _, jwks_body = self.client.request("GET", "/.well-known/genb-gateway-jwks.json")
        self.assertEqual(200, jwks_status)
        self.assertEqual("RSA", json.loads(jwks_body)["keys"][0]["kty"])

    def test_identity_token_is_reused_only_while_safely_inside_its_expiry(self) -> None:
        cookie = self.login()
        first = self.authorize(cookie)[1]["x-genb-identity-token"]
        second = self.authorize(cookie)[1]["x-genb-identity-token"]
        self.assertEqual(first, second)
        self.clock.now += timedelta(seconds=56)
        refreshed = self.authorize(cookie)[1]["x-genb-identity-token"]
        self.assertNotEqual(first, refreshed)
        self.assertGreater(self.app.identity.verify(refreshed, audience="agent-a")["exp"],
                           self.app.identity.verify(first, audience="agent-a")["exp"])

    def test_logout_revokes_both_gateway_and_control_session(self) -> None:
        cookie = self.login()
        status, headers, _ = self.client.request(
            "POST", "/agents/_auth/logout",
            headers={"origin": "http://gateway.local", "cookie": f"genb_gateway_session={cookie}"},
        )
        self.assertEqual(204, status)
        self.assertIn("Max-Age=0", headers["set-cookie"])
        self.assertEqual([("agent-a", "g" * 40)], self.control.revocations)
        self.assertEqual(401, self.authorize(cookie)[0])

    def test_expired_and_permission_revoked_sessions_fail_closed(self) -> None:
        cookie = self.login()
        self.clock.now += timedelta(hours=8, seconds=1)
        self.assertEqual(401, self.authorize(cookie)[0])

        self.setUp()
        cookie = self.login()
        self.app.routes.revoke_user("agent-a", "user-a")
        self.assertEqual(403, self.authorize(cookie)[0])

    def test_internal_auth_ignores_forged_identity_and_upstream_headers(self) -> None:
        cookie = self.login()
        status, headers, body = self.authorize(cookie, extra={
            "x-genb-user-id": "admin", "x-genb-tenant-id": "forged",
            "x-upstream-url": "http://169.254.169.254/latest/meta-data",
        })
        self.assertEqual(204, status, body)
        self.assertEqual("user-a", headers["x-genb-user-id"])
        self.assertEqual("tenant-1", headers["x-genb-tenant-id"])
        self.assertNotIn("169.254.169.254", json.dumps(headers))
        self.assertEqual(401, self.client.request("GET", "/internal/agent-access/authorize?agentId=agent-a&requestPath=%2F")[0])

    def test_open_redirect_path_traversal_and_ssrf_routes_are_rejected(self) -> None:
        invalid_paths = ["https://evil.test/", "/agents/agent-b/", "/agents/agent-a/../agent-b", "/agents/agent-a/%252e%252e/agent-b"]
        for path in invalid_paths:
            status, _, _ = self.client.request("GET", f"/agents/_auth/login?agentId=agent-a&returnPath={path}")
            self.assertEqual(400, status, path)
        with self.assertRaises(ValueError):
            PublishedRouteTable(
                routes=[PublishedAgentRoute("evil", "http://169.254.169.254/latest/meta-data", "NONE", frozenset())],
                allowed_upstreams=frozenset({("127.0.0.1", 19001)}),
            )

    def test_logout_requires_same_origin_and_callback_state_is_single_use(self) -> None:
        cookie = self.login()
        self.assertEqual(403, self.client.request(
            "POST", "/agents/_auth/logout",
            headers={"origin": "http://evil.test", "cookie": f"genb_gateway_session={cookie}"},
        )[0])
        self.assertEqual(401, self.client.request("GET", f"/agents/_auth/callback?code={'a' * 40}&state={'s' * 43}")[0])


if __name__ == "__main__":
    unittest.main()
