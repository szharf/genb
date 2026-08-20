from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import unittest

from genb_gateway.sessions import RedisSessionStore, RespRedisClient


@unittest.skipUnless(os.environ.get("GENB_REDIS_E2E") == "1", "requires isolated local Redis")
class M2RedisSessionTest(unittest.TestCase):
    def test_create_resolve_and_atomic_revoke_use_opaque_hashed_key(self) -> None:
        clock = lambda: datetime.now(timezone.utc)
        redis = RespRedisClient("127.0.0.1", 16380)
        store = RedisSessionStore(redis, clock, namespace="genb:gate-c-test:session:")
        token = store.create(
            ttl=timedelta(minutes=1), session_id="session-1", tenant_id="tenant-1", user_id="user-a",
            username="alice", agent_id="agent-a", session_grant="g" * 40,
        )
        self.assertNotIn("user-a", token)
        self.assertEqual("user-a", store.resolve(token).user_id)
        self.assertTrue(store.is_active(session_id="session-1", tenant_id="tenant-1", user_id="user-a", agent_id="agent-a"))
        self.assertEqual("g" * 40, store.resolve_subject(
            session_id="session-1", tenant_id="tenant-1", user_id="user-a", agent_id="agent-a"
        ).session_grant)
        self.assertEqual("user-a", store.revoke(token).user_id)
        self.assertFalse(store.is_active(session_id="session-1", tenant_id="tenant-1", user_id="user-a", agent_id="agent-a"))
        self.assertIsNone(store.resolve(token))
        self.assertIsNone(store.revoke(token))


if __name__ == "__main__":
    unittest.main()
