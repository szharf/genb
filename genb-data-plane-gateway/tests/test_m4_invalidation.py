from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import unittest

from genb_gateway.app import GatewaySettings, create_app
from genb_gateway.control import FakeControlPlane
from genb_gateway.routing import PublishedRouteTable
from genb_gateway.sessions import InMemorySessionStore


class RuntimeState:
    def __init__(self): self.calls = 0
    def invalidate(self): self.calls += 1; return type("State", (), {"config_version": 9})()


class Tokens:
    def __init__(self): self.invalidations = []
    def invalidate(self, **scope): self.invalidations.append(scope); return 1


class M4InvalidationTest(unittest.TestCase):
    def setUp(self):
        self.clock = lambda: datetime(2026, 8, 13, 11, tzinfo=timezone.utc)
        self.sessions = InMemorySessionStore(self.clock); self.state = RuntimeState(); self.tokens = Tokens()
        self.app = create_app(
            settings=GatewaySettings(
                "http://gateway.local", "http://portal.local", "http://gateway.local/callback", "nginx",
                cookie_secure=False, control_invalidation_token="genb-invalidation-token",
            ), control_plane=FakeControlPlane(), routes=PublishedRouteTable(routes=[], allowed_upstreams=frozenset()),
            clock=self.clock, session_store=self.sessions, runtime_state=self.state, actor_token_cache=self.tokens,
        )

    def post(self, value: dict, token: str = "genb-invalidation-token"):
        sent = []; delivered = False; body = json.dumps(value).encode()
        async def receive():
            nonlocal delivered
            if delivered: return {"type":"http.disconnect"}
            delivered = True; return {"type":"http.request", "body":body, "more_body":False}
        async def send(message): sent.append(message)
        scope = {"type":"http", "method":"POST", "path":"/internal/cache/invalidate", "query_string":b"",
                 "headers":[(b"authorization", ("Bearer " + token).encode())]}
        asyncio.run(self.app(scope, receive, send))
        return sent[0]["status"], b"".join(item.get("body", b"") for item in sent[1:])

    def test_machine_authenticated_config_invalidation_refreshes_snapshot_and_actor_tokens(self):
        self.assertEqual(401, self.post({"schemaVersion":"1.0","scope":"CONFIG","configVersion":9}, "wrong")[0])
        status, body = self.post({"schemaVersion":"1.0","scope":"CONFIG","configVersion":9})
        self.assertEqual(202, status, body)
        self.assertEqual(1, self.state.calls)
        self.assertEqual([{}], self.tokens.invalidations)

    def test_session_invalidation_revokes_gateway_session_and_subject_token_cache(self):
        opaque = self.sessions.create(
            ttl=timedelta(hours=1), session_id="session-a", tenant_id="tenant-1", user_id="user-a",
            username="alice", agent_id="agent-a", session_grant="g" * 40,
        )
        status, _ = self.post({
            "schemaVersion":"1.0", "scope":"SESSION", "configVersion":9,
            "tenantId":"tenant-1", "userId":"user-a", "agentId":"agent-a", "sessionId":"session-a",
        })
        self.assertEqual(202, status)
        self.assertIsNone(self.sessions.resolve(opaque))
        self.assertEqual([{"agent_id":"agent-a", "session_id":"session-a"}], self.tokens.invalidations)

    def test_user_agent_revocation_removes_all_matching_sessions_but_not_another_user(self):
        cookies = []
        for user, session in (("user-a", "session-1"), ("user-a", "session-2"), ("user-b", "session-3")):
            cookies.append(self.sessions.create(
                ttl=timedelta(hours=1), session_id=session, tenant_id="tenant-1", user_id=user,
                username=user, agent_id="agent-a", session_grant=user * 8,
            ))
        status, _ = self.post({
            "schemaVersion":"1.0", "scope":"USER_AGENT", "configVersion":9,
            "tenantId":"tenant-1", "userId":"user-a", "agentId":"agent-a",
        })
        self.assertEqual(202, status)
        self.assertIsNone(self.sessions.resolve(cookies[0])); self.assertIsNone(self.sessions.resolve(cookies[1]))
        self.assertIsNotNone(self.sessions.resolve(cookies[2]))


if __name__ == "__main__": unittest.main()
