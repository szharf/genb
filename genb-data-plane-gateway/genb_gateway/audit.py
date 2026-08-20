from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import threading


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    occurred_at: datetime
    request_id: str
    event_type: str
    outcome: str
    tenant_id: str
    user_id: str
    agent_id: str
    capability_code: str | None = None

    def to_wire(self) -> dict:
        if (not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", self.event_type)
                or self.outcome not in {"SUCCESS", "DENIED", "ERROR"}
                or self.occurred_at.tzinfo is None):
            raise ValueError("invalid audit event")
        subject = hashlib.sha256(
            f"{self.tenant_id}\0{self.user_id}\0{self.agent_id}".encode()
        ).hexdigest()
        value = {
            "eventId":self.event_id, "occurredAt":self.occurred_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "requestId":self.request_id, "eventType":self.event_type, "outcome":self.outcome,
            "actorSubjectHash":"sha256:" + subject, "agentId":self.agent_id,
        }
        if self.capability_code:
            value["capabilityCode"] = self.capability_code
        return value


class InMemoryAuditStore:
    def __init__(self, *, max_length: int) -> None:
        if max_length < 1: raise ValueError("max_length must be positive")
        self.max_length = max_length
        self._items: deque[tuple[str, dict]] = deque()
        self._sequence = 0
        self._lock = threading.Lock()

    def append(self, value: dict) -> bool:
        with self._lock:
            if len(self._items) >= self.max_length: return False
            self._sequence += 1
            self._items.append((str(self._sequence), value))
            return True

    def peek(self, count: int) -> list[tuple[str, dict]]:
        with self._lock: return list(self._items)[:count]

    def delete(self, identifiers: list[str]) -> None:
        with self._lock:
            expected = set(identifiers)
            self._items = deque(item for item in self._items if item[0] not in expected)

    def length(self) -> int:
        with self._lock: return len(self._items)


class RedisAuditStore:
    APPEND_SCRIPT = (
        "if redis.call('XLEN',KEYS[1]) >= tonumber(ARGV[1]) then return nil; end; "
        "return redis.call('XADD',KEYS[1],'*','event',ARGV[2])"
    )

    def __init__(self, redis, *, key: str = "genb:gateway:audit", max_length: int = 10_000) -> None:
        self.redis, self.key, self.max_length = redis, key, max_length

    def append(self, value: dict) -> bool:
        payload = json.dumps(value, separators=(",", ":"), sort_keys=True)
        return self.redis.command("EVAL", self.APPEND_SCRIPT, "1", self.key, str(self.max_length), payload) is not None

    def peek(self, count: int) -> list[tuple[str, dict]]:
        response = self.redis.command("XRANGE", self.key, "-", "+", "COUNT", str(count)) or []
        items = []
        for identifier, fields in response:
            field_map = dict(zip(fields[::2], fields[1::2]))
            items.append((identifier, json.loads(field_map["event"])))
        return items

    def delete(self, identifiers: list[str]) -> None:
        if identifiers:
            self.redis.command("XDEL", self.key, *identifiers)

    def length(self) -> int:
        return int(self.redis.command("XLEN", self.key))


class AuditBuffer:
    """Accepts redacted metadata and performs at most one control-plane attempt per flush."""

    def __init__(self, store, control_plane) -> None:
        self.store, self.control_plane = store, control_plane
        self.dropped_events = 0
        self._lock = threading.Lock()

    def append(self, event: AuditEvent) -> bool:
        accepted = self.store.append(event.to_wire())
        if not accepted:
            with self._lock: self.dropped_events += 1
        return accepted

    def flush(self, *, batch_size: int = 100) -> int:
        batch = self.store.peek(max(1, min(batch_size, 100)))
        if not batch: return 0
        try:
            accepted = self.control_plane.append_audits([item[1] for item in batch])
        except (ConnectionError, OSError):
            return 0
        if accepted != len(batch):
            return 0
        self.store.delete([item[0] for item in batch])
        return accepted
