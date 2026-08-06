import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, TypeVar
from uuid import uuid4

from psycopg2.extras import Json, RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from .config import LongTermMemoryRuntimeConfig
from .extraction import ExtractionCandidate
from .models import ExtractionJob, LongTermMemoryRecord, MemoryScope
from .repository import (
    ExtractionIdempotencyConflict,
    LongTermRepositoryUnavailable,
    normalize_content,
)

T = TypeVar("T")


class PostgreSQLLongTermMemoryRepository:
    """PostgreSQL adapter. Every data operation carries the full tenant/user/agent scope."""

    def __init__(self, dsn: str, *, min_connections: int = 1, max_connections: int = 5) -> None:
        try:
            self._pool = ThreadedConnectionPool(min_connections, max_connections, dsn=dsn)
        except Exception as error:
            raise LongTermRepositoryUnavailable from error

    async def close(self) -> None:
        await asyncio.to_thread(self._pool.closeall)

    async def _run(self, operation: Callable[[Any], T]) -> T:
        def execute() -> T:
            connection = self._pool.getconn()
            try:
                with connection:
                    return operation(connection)
            except Exception as error:
                raise LongTermRepositoryUnavailable from error
            finally:
                self._pool.putconn(connection)

        return await asyncio.to_thread(execute)

    async def health(self) -> bool:
        try:
            return await self._run(lambda connection: _health(connection))
        except LongTermRepositoryUnavailable:
            return False

    async def create_extraction(
        self,
        scope: MemoryScope,
        *,
        turn_id: str,
        user_message: str,
        assistant_message: str,
        occurred_at: datetime,
        idempotency_hash: str,
        request_fingerprint: str,
        config_version_id: int,
        config: LongTermMemoryRuntimeConfig,
    ) -> tuple[ExtractionJob, bool]:
        now = datetime.now(UTC)
        extraction_id = f"ext_{uuid4().hex}"
        config_json = _config_to_json(config)

        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    INSERT INTO memory_extraction_jobs (
                        id, tenant_id, user_id, agent_id, turn_id, user_message,
                        assistant_message, occurred_at, idempotency_hash,
                        request_fingerprint, config_version_id, config_json, status,
                        attempt_count, max_attempts, next_attempt_at, written_count,
                        rejected_count, created_at, updated_at
                    ) VALUES (
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'PENDING',0,%s,%s,0,0,%s,%s
                    )
                    ON CONFLICT (tenant_id, user_id, agent_id, idempotency_hash) DO NOTHING
                    RETURNING *
                    """,
                    (
                        extraction_id, *scope, turn_id, user_message, assistant_message,
                        occurred_at, idempotency_hash, request_fingerprint,
                        config_version_id, Json(config_json), config.max_attempts, now, now, now,
                    ),
                )
                row = cursor.fetchone()
                if row:
                    _event(cursor, row, "ACCEPTED")
                    return _job(row), False
                cursor.execute(
                    """
                    SELECT * FROM memory_extraction_jobs
                    WHERE tenant_id=%s AND user_id=%s AND agent_id=%s AND idempotency_hash=%s
                    """,
                    (*scope, idempotency_hash),
                )
                existing = cursor.fetchone()
                if not existing or existing["request_fingerprint"] != request_fingerprint:
                    raise ExtractionIdempotencyConflict
                return _job(existing), True

        try:
            return await self._run(operation)
        except LongTermRepositoryUnavailable as error:
            if isinstance(error.__cause__, ExtractionIdempotencyConflict):
                raise ExtractionIdempotencyConflict from error
            raise

    async def get_extraction(self, scope: MemoryScope, extraction_id: str) -> ExtractionJob | None:
        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM memory_extraction_jobs WHERE id=%s AND tenant_id=%s AND user_id=%s AND agent_id=%s",
                    (extraction_id, *scope),
                )
                row = cursor.fetchone()
                return _job(row) if row else None

        return await self._run(operation)

    async def claim_extraction(self, extraction_id: str) -> ExtractionJob | None:
        now = datetime.now(UTC)
        lease_until = now + timedelta(seconds=60)

        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    UPDATE memory_extraction_jobs
                    SET status='RUNNING', attempt_count=attempt_count+1,
                        lease_until=%s, updated_at=%s
                    WHERE id=%s AND attempt_count < max_attempts
                      AND next_attempt_at <= %s
                      AND (status='PENDING' OR (status='RUNNING' AND lease_until <= %s))
                    RETURNING *
                    """,
                    (lease_until, now, extraction_id, now, now),
                )
                row = cursor.fetchone()
                if row:
                    _event(cursor, row, "CLAIMED")
                return _job(row) if row else None

        return await self._run(operation)

    async def next_pending_extraction_id(self) -> str | None:
        now = datetime.now(UTC)

        def operation(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM memory_extraction_jobs
                    WHERE next_attempt_at <= %s AND attempt_count < max_attempts
                      AND (status='PENDING' OR (status='RUNNING' AND lease_until <= %s))
                    ORDER BY created_at LIMIT 1
                    """,
                    (now, now),
                )
                row = cursor.fetchone()
                return row[0] if row else None

        return await self._run(operation)

    async def pending_extraction_stats(self) -> tuple[int, float]:
        now = datetime.now(UTC)

        def operation(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*),
                           COALESCE(EXTRACT(EPOCH FROM (%s - min(created_at))), 0)
                    FROM memory_extraction_jobs
                    WHERE status='PENDING'
                       OR (status='RUNNING' AND lease_until <= %s)
                    """,
                    (now, now),
                )
                count, age_seconds = cursor.fetchone()
                return int(count), max(0.0, float(age_seconds))

        return await self._run(operation)

    async def retry_extraction(self, extraction_id: str, *, error_code: str, retry_after_seconds: int) -> str:
        now = datetime.now(UTC)

        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    UPDATE memory_extraction_jobs
                    SET status=CASE WHEN attempt_count >= max_attempts THEN 'DEAD' ELSE 'PENDING' END,
                        error_code=%s, next_attempt_at=%s, lease_until=NULL, updated_at=%s
                    WHERE id=%s AND status='RUNNING' RETURNING *
                    """,
                    (error_code, now + timedelta(seconds=retry_after_seconds), now, extraction_id),
                )
                row = cursor.fetchone()
                if not row:
                    raise RuntimeError("Extraction job is not running")
                _event(cursor, row, row["status"], error_code)
                return row["status"]

        return await self._run(operation)

    async def complete_extraction(
        self,
        extraction_id: str,
        *,
        status: str,
        written_count: int,
        rejected_count: int,
        model: str | None,
        error_code: str | None,
    ) -> None:
        now = datetime.now(UTC)

        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    UPDATE memory_extraction_jobs SET status=%s, written_count=%s,
                        rejected_count=%s, model=%s, error_code=%s, lease_until=NULL,
                        updated_at=%s WHERE id=%s AND status='RUNNING' RETURNING *
                    """,
                    (status, written_count, rejected_count, model, error_code, now, extraction_id),
                )
                row = cursor.fetchone()
                if not row:
                    raise RuntimeError("Extraction job is not running")
                _event(cursor, row, status, error_code)

        await self._run(operation)

    async def upsert_memory(
        self,
        scope: MemoryScope,
        candidate: ExtractionCandidate,
        *,
        retention_days: int,
        source_ref: str,
    ) -> LongTermMemoryRecord:
        import hashlib

        content = normalize_content(candidate.content)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)

        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    INSERT INTO long_term_memories (
                        id, tenant_id, user_id, agent_id, memory_type, content,
                        content_hash, confidence, source_ref, status, first_seen_at,
                        last_confirmed_at, expires_at, created_at, updated_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE',%s,%s,%s,%s,%s)
                    ON CONFLICT (tenant_id, user_id, agent_id, memory_type, content_hash)
                    WHERE status='ACTIVE' DO UPDATE SET
                        confidence=GREATEST(long_term_memories.confidence, EXCLUDED.confidence),
                        last_confirmed_at=EXCLUDED.last_confirmed_at,
                        expires_at=EXCLUDED.expires_at, updated_at=EXCLUDED.updated_at
                    RETURNING *
                    """,
                    (
                        f"mem_{uuid4().hex}", *scope, candidate.memory_type, content,
                        content_hash, candidate.confidence, source_ref, now, now,
                        now + timedelta(days=retention_days), now, now,
                    ),
                )
                return _memory(cursor.fetchone())

        return await self._run(operation)

    async def search(
        self,
        scope: MemoryScope,
        *,
        query: str,
        types: frozenset[str],
        source_types: frozenset[str],
        limit: int,
    ) -> list[LongTermMemoryRecord]:
        if not types or not source_types:
            return []
        now = datetime.now(UTC)
        pattern = f"%{query.replace('%', r'\%').replace('_', r'\_')}%" if query else "%"

        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM long_term_memories
                    WHERE tenant_id=%s AND user_id=%s AND agent_id=%s
                      AND status='ACTIVE' AND expires_at>%s
                      AND memory_type = ANY(%s) AND source_type = ANY(%s)
                      AND content ILIKE %s ESCAPE '\\'
                    ORDER BY confidence DESC, last_confirmed_at DESC LIMIT %s
                    """,
                    (*scope, now, list(types), list(source_types), pattern, limit),
                )
                rows = cursor.fetchall()
                if rows:
                    cursor.execute(
                        "UPDATE long_term_memories SET last_accessed_at=%s WHERE id = ANY(%s) AND tenant_id=%s AND user_id=%s AND agent_id=%s",
                        (now, [row["id"] for row in rows], *scope),
                    )
                return [_memory(row) for row in rows]

        return await self._run(operation)

    async def delete_memory(
        self,
        scope: MemoryScope,
        memory_id: str,
        *,
        actor: str,
        reason: str,
        request_id: str | None,
    ) -> bool:
        now = datetime.now(UTC)

        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    UPDATE long_term_memories SET status='DELETED', deleted_at=%s,
                        deleted_by=%s, delete_reason=%s, updated_at=%s
                    WHERE id=%s AND tenant_id=%s AND user_id=%s AND agent_id=%s
                      AND status!='DELETED' RETURNING *
                    """,
                    (now, actor, reason, now, memory_id, *scope),
                )
                row = cursor.fetchone()
                if not row:
                    return False
                cursor.execute(
                    """
                    INSERT INTO memory_audit_events
                    (tenant_id,user_id,agent_id,memory_id,actor,action,reason,request_id,created_at)
                    VALUES (%s,%s,%s,%s,%s,'DELETE',%s,%s,%s)
                    """,
                    (*scope, memory_id, actor, reason, request_id, now),
                )
                return True

        return await self._run(operation)


def _health(connection) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        return cursor.fetchone()[0] == 1


def _config_to_json(config: LongTermMemoryRuntimeConfig) -> dict[str, object]:
    raw = asdict(config)
    raw["enabled_types"] = sorted(config.enabled_types)
    return raw


def _config_from_json(raw: dict[str, object]) -> LongTermMemoryRuntimeConfig:
    return LongTermMemoryRuntimeConfig(
        enabled_types=frozenset(raw["enabled_types"]),
        auto_extraction_enabled=bool(raw["auto_extraction_enabled"]),
        confidence_threshold=float(raw["confidence_threshold"]),
        retention_days=int(raw["retention_days"]),
        top_k=int(raw["top_k"]),
        max_top_k=int(raw["max_top_k"]),
        model_alias=str(raw["model_alias"]),
        max_attempts=int(raw["max_attempts"]),
    )


def _job(row: dict[str, Any]) -> ExtractionJob:
    raw_config = row["config_json"]
    if isinstance(raw_config, str):
        raw_config = json.loads(raw_config)
    return ExtractionJob(
        extraction_id=row["id"], scope=(row["tenant_id"], row["user_id"], row["agent_id"]),
        turn_id=row["turn_id"], user_message=row["user_message"], assistant_message=row["assistant_message"],
        occurred_at=row["occurred_at"], idempotency_hash=row["idempotency_hash"],
        request_fingerprint=row["request_fingerprint"], config_version_id=row["config_version_id"],
        config=_config_from_json(raw_config), status=row["status"], attempt_count=row["attempt_count"],
        written_count=row["written_count"], rejected_count=row["rejected_count"], model=row["model"],
        error_code=row["error_code"], next_attempt_at=row["next_attempt_at"], lease_until=row["lease_until"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def _memory(row: dict[str, Any]) -> LongTermMemoryRecord:
    return LongTermMemoryRecord(
        memory_id=row["id"], scope=(row["tenant_id"], row["user_id"], row["agent_id"]),
        memory_type=row["memory_type"], content=row["content"], content_hash=row["content_hash"],
        confidence=float(row["confidence"]), source_type=row["source_type"],
        source_ref=row["source_ref"], status=row["status"],
        first_seen_at=row["first_seen_at"], last_confirmed_at=row["last_confirmed_at"],
        last_accessed_at=row["last_accessed_at"], expires_at=row["expires_at"],
    )


def _event(cursor, row: dict[str, Any], event_type: str, result_code: str | None = None) -> None:
    cursor.execute(
        """
        INSERT INTO memory_extraction_events
        (extraction_id,tenant_id,user_id,agent_id,event_type,result_code,written_count,rejected_count,model,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (row["id"], row["tenant_id"], row["user_id"], row["agent_id"], event_type,
         result_code, row["written_count"], row["rejected_count"], row["model"], datetime.now(UTC)),
    )
