from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from genb_gateway.capabilities import (
    AdapterRegistry, AdapterResponse, CapabilityInvocationModule, InvocationProblem, OperationPolicy,
    PublishedCapability, PublishedCapabilityTable,
)
from genb_gateway.identity import IdentityTokens
from genb_gateway.sessions import InMemorySessionStore


class Flaky:
    def __init__(self, failures): self.failures, self.calls = failures, 0
    def invoke(self, request):
        self.calls += 1
        if self.calls <= self.failures: raise ConnectionError("temporary upstream failure")
        return AdapterResponse.json(200, {"ok":True})


class M4UpstreamRetryTest(unittest.TestCase):
    def invoke(self, idempotency: str, adapter: Flaky):
        clock = lambda: datetime(2026, 8, 13, 13, tzinfo=timezone.utc)
        sessions = InMemorySessionStore(clock); identity = IdentityTokens(clock, timedelta(seconds=60))
        opaque = sessions.create(ttl=timedelta(hours=1), session_id="session-a", tenant_id="tenant-1",
                                 user_id="user-a", username="alice", agent_id="agent-a", session_grant="g" * 40)
        registry = AdapterRegistry(); registry.register("FLAKY", "1.0.0", adapter)
        module = CapabilityInvocationModule(
            capabilities=PublishedCapabilityTable([PublishedCapability(
                "agent-a", "SHORT_TERM_MEMORY", "memory-v1", "FLAKY", "1.0.0", "http://memory.local",
                None, "SUBJECT_KEYS", "PUBLISHED", (OperationPolicy("operation", 100, idempotency, "JSON", 4096),),
            )]), adapters=registry, agent_credentials={"agent-a":"machine"}, identity=identity,
            sessions=sessions, clock=clock,
        )
        return module.invoke(
            "SHORT_TERM_MEMORY", "operation", identity.issue(sessions.resolve(opaque)), "machine",
            {"schemaVersion":"1.0", "context":{"requestId":"req-1", "conversationId":"conv-1"}, "payload":{}},
            "idem-1" if idempotency == "REQUIRED_KEY" else None,
        )

    def test_idempotent_read_retries_once_but_never_loops(self):
        recovers = Flaky(1)
        self.assertEqual(200, self.invoke("READ", recovers).status)
        self.assertEqual(2, recovers.calls)
        permanent = Flaky(99)
        with self.assertRaises(InvocationProblem): self.invoke("READ", permanent)
        self.assertEqual(2, permanent.calls)

    def test_write_with_idempotency_key_is_not_automatically_retried(self):
        write = Flaky(99)
        with self.assertRaises(InvocationProblem): self.invoke("REQUIRED_KEY", write)
        self.assertEqual(1, write.calls)


if __name__ == "__main__": unittest.main()
