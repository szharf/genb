from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest

from genb_gateway.audit import AuditBuffer, AuditEvent, InMemoryAuditStore


class Control:
    def __init__(self): self.calls = 0; self.fail = True; self.batches = []
    def append_audits(self, events):
        self.calls += 1
        if self.fail: raise ConnectionError("GenB unavailable")
        self.batches.append(events)
        return len(events)


def event(index: int) -> AuditEvent:
    return AuditEvent(
        event_id=f"event-{index}", occurred_at=datetime(2026, 8, 13, 10, tzinfo=timezone.utc),
        request_id=f"request-{index}", event_type="CAPABILITY_INVOKED", outcome="SUCCESS",
        tenant_id="tenant-private", user_id="user-private", agent_id="agent-a",
        capability_code="SHORT_TERM_MEMORY",
    )


class M4AuditBufferTest(unittest.TestCase):
    def test_bounded_buffer_reports_backpressure_and_wire_event_is_redacted(self) -> None:
        store = InMemoryAuditStore(max_length=2); buffer = AuditBuffer(store, Control())
        self.assertTrue(buffer.append(event(1)))
        self.assertTrue(buffer.append(event(2)))
        self.assertFalse(buffer.append(event(3)))
        self.assertEqual(1, buffer.dropped_events)
        self.assertEqual(2, store.length())
        wire = json.dumps(store.peek(1)[0][1])
        self.assertNotIn("tenant-private", wire)
        self.assertNotIn("user-private", wire)
        self.assertIn("sha256:", wire)

    def test_flush_attempts_once_and_deletes_only_an_accepted_batch(self) -> None:
        control = Control(); store = InMemoryAuditStore(max_length=10); buffer = AuditBuffer(store, control)
        buffer.append(event(1)); buffer.append(event(2))
        self.assertEqual(0, buffer.flush(batch_size=100))
        self.assertEqual(1, control.calls)
        self.assertEqual(2, store.length())

        control.fail = False
        self.assertEqual(2, buffer.flush(batch_size=100))
        self.assertEqual(2, control.calls)
        self.assertEqual(0, store.length())
        self.assertEqual(2, len(control.batches[0]))


if __name__ == "__main__": unittest.main()
