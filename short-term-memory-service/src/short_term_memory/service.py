from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from threading import RLock
from typing import Any, Callable, Protocol, TypeVar

from redis import Redis
from redis.exceptions import WatchError

from .models import CallerScope, ContextPrepareRequest, TurnCommitRequest, WorkbenchUpdate


_SENSITIVE_VALUE = re.compile(
    r"(?i)(password|passwd|pwd|token|access[_-]?token|refresh[_-]?token|验证码)\s*[:=：]\s*([^\s,，;；]+)"
)
T = TypeVar("T")


def redact(value: str) -> str:
    return _SENSITIVE_VALUE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


def redact_nested(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_nested(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_nested(item) for key, item in value.items()}
    return value


@dataclass
class TaskRecord:
    workbench: dict[str, Any] | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=1))
    idempotency: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    dropped_message_count: int = 0


Mutation = Callable[[TaskRecord | None], tuple[TaskRecord | None, T]]


class TaskStore(Protocol):
    name: str

    def read(self, key: str, now: datetime) -> TaskRecord | None: ...
    def mutate(self, key: str, now: datetime, mutation: Mutation[T]) -> T: ...
    def delete(self, key: str) -> bool: ...
    def ready(self) -> bool: ...


class InMemoryTaskStore:
    name = "IN_MEMORY"

    def __init__(self) -> None:
        self._records: dict[str, TaskRecord] = {}
        self._lock = RLock()

    def read(self, key: str, now: datetime) -> TaskRecord | None:
        with self._lock:
            record = self._records.get(key)
            if record is not None and record.expires_at <= now:
                self._records.pop(key, None)
                return None
            return record

    def mutate(self, key: str, now: datetime, mutation: Mutation[T]) -> T:
        with self._lock:
            current = self.read(key, now)
            updated, result = mutation(current)
            if updated is None:
                self._records.pop(key, None)
            else:
                self._records[key] = updated
            return result

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._records.pop(key, None) is not None

    def ready(self) -> bool:
        return True


class RedisTaskStore:
    """Stores one atomic JSON document per isolated task using Redis optimistic locking."""

    name = "REDIS"

    def __init__(self, client: Redis, prefix: str = "genb:short-term-memory:v1") -> None:
        self._client = client
        self._prefix = prefix.rstrip(":")

    def read(self, key: str, now: datetime) -> TaskRecord | None:
        raw = self._client.get(self._redis_key(key))
        if raw is None:
            return None
        record = self._decode(raw)
        if record.expires_at <= now:
            self._client.delete(self._redis_key(key))
            return None
        return record

    def mutate(self, key: str, now: datetime, mutation: Mutation[T]) -> T:
        redis_key = self._redis_key(key)
        for _ in range(5):
            with self._client.pipeline() as pipe:
                try:
                    pipe.watch(redis_key)
                    raw = pipe.get(redis_key)
                    current = None if raw is None else self._decode(raw)
                    if current is not None and current.expires_at <= now:
                        current = None
                    updated, result = mutation(current)
                    pipe.multi()
                    if updated is None:
                        pipe.delete(redis_key)
                    else:
                        ttl = max(1, int((updated.expires_at - now).total_seconds()))
                        pipe.set(redis_key, self._encode(updated), ex=ttl)
                    pipe.execute()
                    return result
                except WatchError:
                    continue
        raise RuntimeError("REDIS_CONCURRENT_UPDATE_FAILED")

    def delete(self, key: str) -> bool:
        return bool(self._client.delete(self._redis_key(key)))

    def ready(self) -> bool:
        return bool(self._client.ping())

    def _redis_key(self, isolated_key: str) -> str:
        digest = hashlib.sha256(isolated_key.encode("utf-8")).hexdigest()
        return f"{self._prefix}:task:{digest}"

    @staticmethod
    def _encode(record: TaskRecord) -> str:
        document = asdict(record)
        document["expires_at"] = record.expires_at.isoformat()
        return json.dumps(document, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode(raw: bytes | str) -> TaskRecord:
        document = json.loads(raw)
        return TaskRecord(
            workbench=document.get("workbench"),
            messages=document.get("messages", []),
            expires_at=datetime.fromisoformat(document["expires_at"]),
            idempotency=document.get("idempotency", {}),
            dropped_message_count=document.get("dropped_message_count", 0),
        )


class ShortTermMemoryService:
    """Owns isolation, expiry and task recovery behind a storage-independent interface."""

    def __init__(
        self,
        store: TaskStore | None = None,
        clock: Callable[[], datetime] | None = None,
        *,
        max_stored_messages: int = 200,
    ) -> None:
        if max_stored_messages < 2 or max_stored_messages % 2 != 0:
            raise ValueError("max_stored_messages must be an even integer of at least 2")
        self.store = store or InMemoryTaskStore()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._max_stored_messages = max_stored_messages

    def save_workbench(self, scope: CallerScope, task_id: str, update: WorkbenchUpdate) -> dict[str, Any]:
        now = self._clock()

        def apply(record: TaskRecord | None) -> tuple[TaskRecord, dict[str, Any]]:
            current = record or TaskRecord(expires_at=now + timedelta(days=1))
            current.workbench = redact_nested(update.model_dump(mode="json", by_alias=True, exclude={"expires_in_seconds"}))
            current.expires_at = now + timedelta(seconds=update.expires_in_seconds)
            return current, self._workbench_view(task_id, current)

        return self.store.mutate(self._key(scope, task_id), now, apply)

    def commit_turn(self, scope: CallerScope, request: TurnCommitRequest, idempotency_key: str) -> dict[str, Any]:
        payload = request.model_dump(mode="json", by_alias=True)
        now = self._clock()

        def apply(record: TaskRecord | None) -> tuple[TaskRecord, dict[str, Any]]:
            current = record or TaskRecord(expires_at=now + timedelta(days=1))
            replay = current.idempotency.get(idempotency_key)
            if replay is not None:
                previous_payload, previous_result = replay
                if previous_payload != payload:
                    raise ValueError("IDEMPOTENCY_CONFLICT")
                return current, {**previous_result, "replayed": True}
            occurred_at = request.occurred_at.isoformat().replace("+00:00", "Z")
            current.messages.extend([
                {"turnId": request.turn_id, "sessionId": request.session_id, "role": "user", "content": redact(request.user_message), "occurredAt": occurred_at},
                {"turnId": request.turn_id, "sessionId": request.session_id, "role": "assistant", "content": redact(request.assistant_message), "occurredAt": occurred_at},
            ])
            overflow = max(0, len(current.messages) - self._max_stored_messages)
            if overflow:
                del current.messages[:overflow]
                current.dropped_message_count += overflow
            result = {"taskId": request.task_id, "messageCount": len(current.messages), "replayed": False}
            current.idempotency[idempotency_key] = [payload, result]
            return current, result

        return self.store.mutate(self._key(scope, request.task_id), now, apply)

    def prepare_context(self, scope: CallerScope, request: ContextPrepareRequest) -> dict[str, Any]:
        record = self.store.read(self._key(scope, request.task_id), self._clock())
        if record is None:
            return {
                "taskId": request.task_id,
                "sessionId": request.session_id,
                "messages": [],
                "workbench": None,
                "trimmedMessageCount": 0,
            }
        selected_groups: list[list[dict[str, Any]]] = []
        for index in range(len(record.messages) - 1, -1, -2):
            group = record.messages[max(0, index - 1):index + 1]
            if len(group) != 2 or len(selected_groups) * 2 + 2 > request.max_messages:
                break
            selected_groups.append(group)
        selected = [message for group in reversed(selected_groups) for message in group]
        return {
            "taskId": request.task_id,
            "sessionId": request.session_id,
            "messages": selected,
            "workbench": record.workbench,
            "trimmedMessageCount": record.dropped_message_count + len(record.messages) - len(selected),
        }

    def get_task(self, scope: CallerScope, task_id: str) -> dict[str, Any] | None:
        record = self.store.read(self._key(scope, task_id), self._clock())
        return None if record is None else self._workbench_view(task_id, record)

    def delete_task(self, scope: CallerScope, task_id: str) -> bool:
        return self.store.delete(self._key(scope, task_id))

    @staticmethod
    def _key(scope: CallerScope, task_id: str) -> str:
        return "\x1f".join((scope.tenant_id, scope.agent_id, scope.user_id, task_id))

    @staticmethod
    def _workbench_view(task_id: str, record: TaskRecord) -> dict[str, Any]:
        return {"taskId": task_id, "workbench": record.workbench, "expiresAt": record.expires_at.isoformat().replace("+00:00", "Z")}
