from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
import json

from genb_gateway.sessions import GatewaySession, L1SessionStore, InMemorySessionStore, RedisSessionStore


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
    def test_redis_session_decoding_preserves_creation_time_and_accepts_legacy_records(self):
        clock = Clock(); original = Backend(clock).session
        record = {**original.__dict__, 'expires_at': original.expires_at.isoformat()}
        record.pop('created_at')
        self.assertIsNone(RedisSessionStore._decode(json.dumps(record)).created_at)
        record['created_at'] = clock().isoformat()
        self.assertEqual(clock(), RedisSessionStore._decode(json.dumps(record)).created_at)

    def test_reauthorized_new_session_works_without_reviving_revoked_sessions(self):
        for scope in ('access', 'agent'):
            with self.subTest(scope=scope):
                clock = Clock(); backend = InMemorySessionStore(clock); store = L1SessionStore(backend, clock)
                subject = dict(tenant_id='tenant-1', user_id='user-a', username='alice', agent_id='agent-a', session_grant='g' * 40)
                old = store.create(ttl=timedelta(hours=1), session_id='old', **subject)
                self.assertIsNotNone(store.resolve(old))
                revoke = (lambda: store.revoke_access(tenant_id='tenant-1', user_id='user-a', agent_id='agent-a')) if scope == 'access' else (lambda: store.revoke_agent(agent_id='agent-a'))
                revoke(); clock.advance(1)
                fresh = store.create(ttl=timedelta(hours=1), session_id='fresh', **subject)
                self.assertIsNone(store.resolve(old))
                self.assertIsNotNone(store.resolve(fresh))
                self.assertIsNotNone(store.resolve_subject(session_id='fresh', tenant_id='tenant-1', user_id='user-a', agent_id='agent-a'))
                revoke()
                self.assertIsNone(store.resolve(fresh))

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
