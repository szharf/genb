from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from genb_gateway.sessions import GatewaySession, L1SessionStore


class Clock:
    def __init__(self): self.now = datetime(2026, 8, 13, 12, tzinfo=timezone.utc)
    def __call__(self): return self.now
    def advance(self, seconds): self.now += timedelta(seconds=seconds)


class Backend:
    def __init__(self, clock):
        self.clock, self.fail = clock, False
        self.session = GatewaySession("session-a", "tenant-1", "user-a", "alice", "agent-a", "g" * 40,
                                      clock() + timedelta(hours=1))
    def resolve(self, token):
        if self.fail: raise ConnectionError("Redis unavailable")
        return self.session if token == "opaque" else None
    def resolve_subject(self, **subject):
        if self.fail: raise ConnectionError("Redis unavailable")
        return self.session if subject["session_id"] == "session-a" else None
    def create(self, **kwargs):
        if self.fail: raise ConnectionError("Redis unavailable")
        return "new-opaque"
    def revoke(self, token):
        if self.fail: raise ConnectionError("Redis unavailable")
        return self.session
    def revoke_subject(self, **subject): return 1
    def revoke_access(self, **subject):
        if self.fail: raise ConnectionError("Redis unavailable")
        return 1
    def revoke_agent(self, **subject): return 1


class M4SessionCacheTest(unittest.TestCase):
    def test_l1_hit_avoids_redis_but_never_exceeds_five_seconds_during_failure(self):
        clock = Clock(); backend = Backend(clock); store = L1SessionStore(backend, clock, ttl=timedelta(seconds=5))
        self.assertEqual("user-a", store.resolve("opaque").user_id)
        backend.fail = True
        self.assertEqual("user-a", store.resolve("opaque").user_id)
        clock.advance(5,)
        with self.assertRaises(ConnectionError): store.resolve("opaque")
        with self.assertRaises(ConnectionError): store.create(ttl=timedelta(hours=1))

    def test_active_user_agent_invalidation_removes_l1_before_backend_result(self):
        clock = Clock(); backend = Backend(clock); store = L1SessionStore(backend, clock)
        store.resolve("opaque")
        backend.fail = True
        with self.assertRaises(ConnectionError):
            store.revoke_access(tenant_id="tenant-1", user_id="user-a", agent_id="agent-a")
        with self.assertRaises(ConnectionError): store.resolve("opaque")
        backend.fail = False
        self.assertIsNone(store.resolve("opaque"))
        self.assertIsNone(store.resolve_subject(session_id="session-a", tenant_id="tenant-1",
                                                user_id="user-a", agent_id="agent-a"))


if __name__ == "__main__": unittest.main()
