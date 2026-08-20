from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from genb_gateway.runtime_state import (
    ConfigurationUnavailable, ControlSnapshotModule, InMemorySnapshotStore,
)


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 13, 8, tzinfo=timezone.utc)
    def __call__(self): return self.now
    def advance(self, **kwargs): self.now += timedelta(**kwargs)


def snapshot(version: int, *, status: str = "PUBLISHED", with_agent: bool = False) -> dict:
    return {
        "schemaVersion":"1.0", "configVersion":version, "publishedAt":"2026-08-13T08:00:00Z",
        "agents":([{
            "agentId":"agent-a", "status":"PUBLISHED", "upstreamRef":"http://agent.internal:18714/",
            "identityMode":"SIGNED_TOKEN",
        }] if with_agent else []),
        "implementations":[{
            "implementationCode":"memory-v1", "capabilityCode":"SHORT_TERM_MEMORY",
            "providerServiceName":"Memory", "adapterCode":"SHORT_TERM_MEMORY_HTTP", "adapterVersion":"1.0.0",
            "upstreamRef":"http://memory.internal:8701", "credentialRef":"env://MEMORY_TOKEN",
            "isolationMode":"SUBJECT_KEYS", "status":status, "operations":[{
                "operationId":"prepareShortTermContext", "timeoutMs":1000, "idempotency":"READ",
                "responseMode":"JSON", "maxRequestBytes":4096,
            }],
        }],
        "bindings":[{
            "agentId":"agent-a", "capabilityCode":"SHORT_TERM_MEMORY", "implementationCode":"memory-v1",
            "bindingVersion":version, "status":"ACTIVE",
        }],
    }


class MutableSource:
    def __init__(self, value: dict) -> None:
        self.value = value; self.version = value["configVersion"]; self.fail = False
        self.version_reads = 0; self.snapshot_reads = 0
    def get_version(self) -> int:
        self.version_reads += 1
        if self.fail: raise ConnectionError("GenB unavailable")
        return self.version
    def get_snapshot(self) -> dict:
        self.snapshot_reads += 1
        if self.fail: raise ConnectionError("GenB unavailable")
        return self.value


class M4RuntimeStateTest(unittest.TestCase):
    def test_incomplete_or_mixed_new_snapshot_never_replaces_last_known_good(self) -> None:
        clock = MutableClock(); source = MutableSource(snapshot(1)); store = InMemorySnapshotStore()
        module = ControlSnapshotModule(source=source, store=store, clock=clock)
        module.refresh(force=True)
        self.assertEqual(1, module.current(risk="HIGH").config_version)
        self.assertEqual("memory-v1", module.resolve("agent-a", "SHORT_TERM_MEMORY").implementation_code)

        source.version = 2
        source.value = snapshot(3)
        with self.assertRaises(ConfigurationUnavailable): module.refresh(force=True)

        current = module.current(risk="LOW")
        self.assertEqual(1, current.config_version)
        self.assertEqual(1, store.load().snapshot["configVersion"])
        self.assertEqual("memory-v1", module.resolve("agent-a", "SHORT_TERM_MEMORY").implementation_code)

    def test_two_second_polling_high_risk_fail_closed_and_low_risk_grace_has_hard_limit(self) -> None:
        clock = MutableClock(); source = MutableSource(snapshot(1)); store = InMemorySnapshotStore()
        module = ControlSnapshotModule(source=source, store=store, clock=clock)
        module.start()
        self.assertEqual(1, source.version_reads)
        for _ in range(5): module.resolve("agent-a", "SHORT_TERM_MEMORY")
        self.assertEqual(1, source.version_reads)

        clock.advance(seconds=2); source.fail = True
        self.assertEqual("memory-v1", module.resolve("agent-a", "SHORT_TERM_MEMORY").implementation_code)
        self.assertEqual(2, source.version_reads)
        clock.advance(seconds=3, milliseconds=1)
        with self.assertRaises(ConfigurationUnavailable):
            module.resolve("agent-a", "SHORT_TERM_MEMORY")
        self.assertEqual(1, module.current(risk="LOW").config_version)
        clock.advance(minutes=14, seconds=57)
        with self.assertRaises(ConfigurationUnavailable): module.current(risk="LOW")

    def test_restart_restores_one_complete_last_known_good_then_recovers_to_latest(self) -> None:
        clock = MutableClock(); source = MutableSource(snapshot(4)); store = InMemorySnapshotStore()
        ControlSnapshotModule(source=source, store=store, clock=clock).start()
        clock.advance(seconds=3); source.fail = True
        restarted = ControlSnapshotModule(source=source, store=store, clock=clock)
        restored = restarted.start()
        self.assertEqual(4, restored.config_version)
        self.assertEqual(4, restarted.current(risk="LOW").config_version)

        source.fail = False; source.version = 5; source.value = snapshot(5, status="DISABLED")
        recovered = restarted.invalidate()
        self.assertEqual(5, recovered.config_version)
        self.assertEqual("DISABLED", restarted.resolve("agent-a", "SHORT_TERM_MEMORY").status)

    def test_agent_route_and_capability_binding_are_published_from_the_same_version(self) -> None:
        clock = MutableClock(); source = MutableSource(snapshot(6, with_agent=True))
        module = ControlSnapshotModule(
            source=source, store=InMemorySnapshotStore(), clock=clock,
            allowed_upstreams=frozenset({("agent.internal", 18714)}),
        )
        state = module.start()
        self.assertEqual(6, state.config_version)
        self.assertEqual("http://agent.internal:18714", module.resolve("agent-a").upstream)
        self.assertEqual(6, module.resolve("agent-a", "SHORT_TERM_MEMORY").binding_version)


if __name__ == "__main__": unittest.main()
