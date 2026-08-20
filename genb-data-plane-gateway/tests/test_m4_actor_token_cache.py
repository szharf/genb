from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from genb_gateway.tokens import ActorTokenLease, CachingActorTokenProvider
from genb_gateway.sessions import GatewaySession


class Clock:
    def __init__(self): self.now = datetime(2026, 8, 13, 9, tzinfo=timezone.utc)
    def __call__(self): return self.now
    def advance(self, seconds): self.now += timedelta(seconds=seconds)


class Issuer:
    def __init__(self, clock): self.clock = clock; self.calls = 0; self.fail = False
    def issue_lease(self, session, capability):
        self.calls += 1
        if self.fail: raise ConnectionError("control unavailable")
        return ActorTokenLease(f"actor-{self.calls}", self.clock() + timedelta(minutes=5), self.binding_version)
    binding_version = 7


class M4ActorTokenCacheTest(unittest.TestCase):
    def test_cache_key_includes_subject_capability_and_binding_and_never_serves_expired_token(self) -> None:
        clock = Clock(); issuer = Issuer(clock)
        cache = CachingActorTokenProvider(issuer, clock, max_ttl=timedelta(minutes=5), safety_margin=timedelta(seconds=5))
        session = GatewaySession("session-a", "tenant-1", "user-a", "alice", "agent-a", "g" * 40,
                                 clock() + timedelta(hours=1))
        self.assertEqual("actor-1", cache.issue(session, "SHORT_TERM_MEMORY", 7))
        self.assertEqual("actor-1", cache.issue(session, "SHORT_TERM_MEMORY", 7))
        self.assertEqual(1, issuer.calls)

        issuer.binding_version = 8
        self.assertEqual("actor-2", cache.issue(session, "SHORT_TERM_MEMORY", 8))
        self.assertEqual(2, issuer.calls)
        cache.invalidate(agent_id="agent-a", capability_code="SHORT_TERM_MEMORY")
        self.assertEqual("actor-3", cache.issue(session, "SHORT_TERM_MEMORY", 8))

        clock.advance(296); issuer.fail = True
        with self.assertRaises(ConnectionError): cache.issue(session, "SHORT_TERM_MEMORY", 8)
        self.assertEqual(4, issuer.calls)

    def test_two_users_never_share_actor_token(self) -> None:
        clock = Clock(); issuer = Issuer(clock); cache = CachingActorTokenProvider(issuer, clock)
        def session(user): return GatewaySession("session-" + user, "tenant-1", user, user, "agent-a", user * 40,
                                                  clock() + timedelta(hours=1))
        first = cache.issue(session("a"), "SHORT_TERM_MEMORY", 7)
        second = cache.issue(session("b"), "SHORT_TERM_MEMORY", 7)
        self.assertNotEqual(first, second)
        self.assertEqual(2, issuer.calls)


if __name__ == "__main__": unittest.main()
