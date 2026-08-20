from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import unittest
from uuid import uuid4

from genb_gateway.audit import AuditBuffer, AuditEvent, RedisAuditStore
from genb_gateway.runtime_state import RedisSnapshotStore
from genb_gateway.sessions import RedisSessionStore, RespRedisClient


class Control:
    def append_audits(self, events): return len(events)


@unittest.skipUnless(os.environ.get("GENB_REDIS_E2E") == "1", "requires isolated local Redis")
class M4RedisStateTest(unittest.TestCase):
    def test_snapshot_session_revocation_and_bounded_audit_survive_real_redis(self):
        redis = RespRedisClient("127.0.0.1", 16380); prefix = "genb:gate-e:" + uuid4().hex + ":"
        now = datetime.now(timezone.utc)
        snapshot_store = RedisSnapshotStore(redis, key=prefix + "snapshot")
        snapshot_store.save({"schemaVersion":"1.0", "configVersion":3}, now)
        self.assertEqual(3, snapshot_store.load().snapshot["configVersion"])

        sessions = RedisSessionStore(redis, lambda: now, namespace=prefix + "session:")
        tokens = [sessions.create(
            ttl=timedelta(minutes=2), session_id=f"session-{index}", tenant_id="tenant-1",
            user_id="user-a", username="alice", agent_id="agent-a", session_grant="g" * 40,
        ) for index in range(2)]
        self.assertEqual(2, sessions.revoke_access(tenant_id="tenant-1", user_id="user-a", agent_id="agent-a"))
        self.assertTrue(all(sessions.resolve(token) is None for token in tokens))
        agent_tokens = [sessions.create(
            ttl=timedelta(minutes=2), session_id=f"agent-session-{index}", tenant_id="tenant-1",
            user_id=f"user-{index}", username="user", agent_id="agent-a", session_grant="h" * 40,
        ) for index in range(2)]
        self.assertEqual(2, sessions.revoke_agent(agent_id="agent-a"))
        self.assertTrue(all(sessions.resolve(token) is None for token in agent_tokens))

        audit_store = RedisAuditStore(redis, key=prefix + "audit", max_length=2)
        audit = AuditBuffer(audit_store, Control())
        make = lambda index: AuditEvent(
            f"event-{index}", now, f"request-{index}", "CAPABILITY_INVOKED", "SUCCESS",
            "tenant-1", "user-a", "agent-a", "SHORT_TERM_MEMORY",
        )
        self.assertTrue(audit.append(make(1))); self.assertTrue(audit.append(make(2)))
        self.assertFalse(audit.append(make(3))); self.assertEqual(2, audit_store.length())
        self.assertEqual(2, audit.flush()); self.assertEqual(0, audit_store.length())
        redis.command("DEL", prefix + "snapshot")


if __name__ == "__main__": unittest.main()
