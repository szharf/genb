import hashlib
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, TypeVar
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from .extraction import ExtractionCandidate
from .models import ExtractionJob, LongTermMemoryRecord, MemoryScope
from .repository import (
    ConversationMemoryRepositoryUnavailable,
    ExtractionIdempotencyConflict,
)


T = TypeVar("T")
SCHEMA = "long_term_memory_service"


class PostgreSQLConversationMemoryRepository:
    """Conversation Memory PostgreSQL Adapter; every public data query carries full scope."""

    def __init__(
        self,
        dsn: str,
        *,
        min_connections: int = 1,
        max_connections: int = 5,
    ) -> None:
        try:
            self._pool = ThreadedConnectionPool(
                min_connections, max_connections, dsn=dsn
            )
        except psycopg2.Error as error:
            raise ConversationMemoryRepositoryUnavailable from error

    def close(self) -> None:
        self._pool.closeall()

    def _run(self, operation: Callable[[object], T]) -> T:
        connection = self._pool.getconn()
        try:
            with connection:
                return operation(connection)
        except psycopg2.Error as error:
            raise ConversationMemoryRepositoryUnavailable from error
        finally:
            self._pool.putconn(connection)

    def ensure_schema(self) -> None:
        migration = (
            Path(__file__).resolve().parents[2] / "migrations" / "001_initial.sql"
        ).read_text("utf-8")

        def operation(connection) -> None:
            with connection.cursor() as cursor:
                cursor.execute(migration)

        self._run(operation)

    def health(self) -> bool:
        try:
            return self._run(_health)
        except ConversationMemoryRepositoryUnavailable:
            return False

    def create_extraction(self, job: ExtractionJob) -> tuple[ExtractionJob, bool]:
        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.memory_extraction_jobs (
                        id, tenant_id, user_id, agent_id, conversation_id, turn_id,
                        user_message, assistant_message, occurred_at, idempotency_hash,
                        request_fingerprint, status, attempt_count, max_attempts,
                        next_attempt_at, lease_until, written_count, rejected_count,
                        error_code, created_at, updated_at
                    ) VALUES (
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                    )
                    ON CONFLICT (tenant_id, user_id, agent_id, idempotency_hash)
                    DO NOTHING RETURNING *
                    """,
                    _job_parameters(job),
                )
                row = cursor.fetchone()
                if row is not None:
                    return _job(row), False
                cursor.execute(
                    f"""
                    SELECT * FROM {SCHEMA}.memory_extraction_jobs
                    WHERE tenant_id=%s AND user_id=%s AND agent_id=%s
                      AND idempotency_hash=%s
                    """,
                    (*job.scope, job.idempotency_hash),
                )
                existing = cursor.fetchone()
                if (
                    existing is None
                    or existing["request_fingerprint"] != job.request_fingerprint
                ):
                    raise ExtractionIdempotencyConflict
                return _job(existing), True

        return self._run(operation)

    def get_extraction(
        self, scope: MemoryScope, extraction_id: str
    ) -> ExtractionJob | None:
        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    f"""
                    SELECT * FROM {SCHEMA}.memory_extraction_jobs
                    WHERE id=%s AND tenant_id=%s AND user_id=%s AND agent_id=%s
                    """,
                    (extraction_id, *scope),
                )
                row = cursor.fetchone()
                return _job(row) if row else None

        return self._run(operation)

    def get_extraction_by_id(self, extraction_id: str) -> ExtractionJob | None:
        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    f"SELECT * FROM {SCHEMA}.memory_extraction_jobs WHERE id=%s",
                    (extraction_id,),
                )
                row = cursor.fetchone()
                return _job(row) if row else None

        return self._run(operation)

    def claim_extraction(
        self, extraction_id: str, *, lease_seconds: int
    ) -> ExtractionJob | None:
        now = datetime.now(UTC)

        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    f"""
                    UPDATE {SCHEMA}.memory_extraction_jobs
                    SET status='RUNNING', attempt_count=attempt_count+1,
                        lease_until=%s, updated_at=%s
                    WHERE id=%s AND attempt_count < max_attempts
                      AND next_attempt_at <= %s
                      AND (
                        status='PENDING'
                        OR (status='RUNNING' AND lease_until IS NOT NULL AND lease_until <= %s)
                      )
                    RETURNING *
                    """,
                    (
                        now + timedelta(seconds=lease_seconds),
                        now,
                        extraction_id,
                        now,
                        now,
                    ),
                )
                row = cursor.fetchone()
                return _job(row) if row else None

        return self._run(operation)

    def complete_extraction(
        self,
        extraction_id: str,
        *,
        status: str,
        written_count: int,
        rejected_count: int,
        error_code: str | None,
    ) -> None:
        now = datetime.now(UTC)

        def operation(connection) -> None:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {SCHEMA}.memory_extraction_jobs
                    SET status=%s, written_count=%s, rejected_count=%s,
                        error_code=%s, lease_until=NULL, updated_at=%s
                    WHERE id=%s AND status='RUNNING'
                    """,
                    (
                        status,
                        written_count,
                        rejected_count,
                        error_code,
                        now,
                        extraction_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("Extraction job is not running")

        self._run(operation)

    def retry_extraction(
        self,
        extraction_id: str,
        *,
        error_code: str,
        retry_after_seconds: int,
    ) -> str:
        now = datetime.now(UTC)

        def operation(connection) -> str:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {SCHEMA}.memory_extraction_jobs
                    SET status=CASE WHEN attempt_count >= max_attempts THEN 'DEAD' ELSE 'PENDING' END,
                        error_code=%s, next_attempt_at=%s, lease_until=NULL, updated_at=%s
                    WHERE id=%s AND status='RUNNING'
                    RETURNING status
                    """,
                    (
                        error_code,
                        now + timedelta(seconds=retry_after_seconds),
                        now,
                        extraction_id,
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("Extraction job is not running")
                return str(row[0])

        return self._run(operation)

    def upsert_memory(
        self,
        scope: MemoryScope,
        candidate: ExtractionCandidate,
        *,
        source_ref: str,
        retention_days: int,
    ) -> LongTermMemoryRecord:
        normalized = unicodedata.normalize("NFKC", candidate.content).casefold().strip()
        content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)

        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.long_term_memories (
                        id, tenant_id, user_id, agent_id, memory_type, content,
                        content_hash, confidence, source_type, source_ref, status,
                        last_confirmed_at, expires_at, created_at, updated_at
                    ) VALUES (
                        %s,%s,%s,%s,%s,%s,%s,%s,'CONVERSATION',%s,'ACTIVE',%s,%s,%s,%s
                    )
                    ON CONFLICT (tenant_id, user_id, agent_id, memory_type, content_hash)
                    WHERE status='ACTIVE' DO UPDATE SET
                        confidence=GREATEST(long_term_memories.confidence, EXCLUDED.confidence),
                        source_ref=EXCLUDED.source_ref,
                        last_confirmed_at=EXCLUDED.last_confirmed_at,
                        expires_at=EXCLUDED.expires_at,
                        updated_at=EXCLUDED.updated_at
                    RETURNING *
                    """,
                    (
                        f"mem_{uuid4().hex}",
                        *scope,
                        candidate.memory_type,
                        candidate.content,
                        content_hash,
                        candidate.confidence,
                        source_ref,
                        now,
                        now + timedelta(days=retention_days),
                        now,
                        now,
                    ),
                )
                return _memory(cursor.fetchone())

        return self._run(operation)

    def search(
        self,
        scope: MemoryScope,
        *,
        query: str,
        types: frozenset[str] | None,
        source_types: frozenset[str],
        limit: int,
    ) -> list[LongTermMemoryRecord]:
        if not source_types:
            return []
        now = datetime.now(UTC)
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        type_values = list(types) if types else None

        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    f"""
                    SELECT * FROM {SCHEMA}.long_term_memories
                    WHERE tenant_id=%s AND user_id=%s AND agent_id=%s
                      AND status='ACTIVE' AND expires_at>%s
                      AND (%s::text[] IS NULL OR memory_type = ANY(%s))
                      AND source_type = ANY(%s)
                      AND content ILIKE %s ESCAPE '\\'
                    ORDER BY confidence DESC, last_confirmed_at DESC
                    LIMIT %s
                    """,
                    (
                        *scope,
                        now,
                        type_values,
                        type_values,
                        list(source_types),
                        pattern,
                        limit,
                    ),
                )
                return [_memory(row) for row in cursor.fetchall()]

        return self._run(operation)

    def delete_memory(
        self,
        scope: MemoryScope,
        memory_id: str,
        *,
        actor: str,
        reason: str,
    ) -> bool:
        now = datetime.now(UTC)

        def operation(connection) -> bool:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {SCHEMA}.long_term_memories
                    SET status='DELETED', deleted_at=%s, deleted_by=%s,
                        delete_reason=%s, updated_at=%s
                    WHERE id=%s AND tenant_id=%s AND user_id=%s AND agent_id=%s
                      AND status='ACTIVE'
                    """,
                    (now, actor, reason, now, memory_id, *scope),
                )
                if cursor.rowcount != 1:
                    return False
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.memory_audit_events
                    (tenant_id,user_id,agent_id,memory_id,actor,action,reason,created_at)
                    VALUES (%s,%s,%s,%s,%s,'DELETE',%s,%s)
                    """,
                    (*scope, memory_id, actor, reason, now),
                )
                return True

        return self._run(operation)

    def correct_memory(
        self,
        scope: MemoryScope,
        memory_id: str,
        *,
        content: str,
        actor: str,
        reason: str,
        retention_days: int,
    ) -> LongTermMemoryRecord | None:
        normalized = unicodedata.normalize("NFKC", content).casefold().strip()
        content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)

        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    f"""
                    SELECT * FROM {SCHEMA}.long_term_memories
                    WHERE id=%s AND tenant_id=%s AND user_id=%s AND agent_id=%s
                      AND status='ACTIVE'
                    FOR UPDATE
                    """,
                    (memory_id, *scope),
                )
                original = cursor.fetchone()
                if original is None:
                    return None
                cursor.execute(
                    f"""
                    UPDATE {SCHEMA}.long_term_memories
                    SET status='SUPERSEDED', updated_at=%s
                    WHERE id=%s
                    """,
                    (now, memory_id),
                )
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.long_term_memories (
                        id, tenant_id, user_id, agent_id, memory_type, content,
                        content_hash, confidence, source_type, source_ref, status,
                        last_confirmed_at, expires_at, created_at, updated_at
                    ) VALUES (
                        %s,%s,%s,%s,%s,%s,%s,%s,'CONVERSATION',%s,'ACTIVE',%s,%s,%s,%s
                    )
                    ON CONFLICT (tenant_id, user_id, agent_id, memory_type, content_hash)
                    WHERE status='ACTIVE' DO UPDATE SET
                        confidence=GREATEST(long_term_memories.confidence, EXCLUDED.confidence),
                        source_ref=EXCLUDED.source_ref,
                        last_confirmed_at=EXCLUDED.last_confirmed_at,
                        expires_at=EXCLUDED.expires_at,
                        updated_at=EXCLUDED.updated_at
                    RETURNING *
                    """,
                    (
                        f"mem_{uuid4().hex}",
                        *scope,
                        original["memory_type"],
                        content,
                        content_hash,
                        original["confidence"],
                        f"correction:{memory_id}",
                        now,
                        now + timedelta(days=retention_days),
                        now,
                        now,
                    ),
                )
                corrected = cursor.fetchone()
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.memory_audit_events
                    (tenant_id,user_id,agent_id,memory_id,actor,action,reason,created_at)
                    VALUES (%s,%s,%s,%s,%s,'CORRECT',%s,%s)
                    """,
                    (*scope, memory_id, actor, reason, now),
                )
                return _memory(corrected)

        return self._run(operation)

    def record_feedback(
        self,
        scope: MemoryScope,
        memory_id: str,
        *,
        action: str,
        actor: str,
        reason: str,
        retention_days: int,
    ) -> LongTermMemoryRecord | None:
        now = datetime.now(UTC)

        def operation(connection):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                if action == "CONFIRM":
                    cursor.execute(
                        f"""
                        UPDATE {SCHEMA}.long_term_memories
                        SET confidence=LEAST(1.0, confidence + 0.05),
                            last_confirmed_at=%s, expires_at=%s, updated_at=%s
                        WHERE id=%s AND tenant_id=%s AND user_id=%s AND agent_id=%s
                          AND status='ACTIVE'
                        RETURNING *
                        """,
                        (
                            now,
                            now + timedelta(days=retention_days),
                            now,
                            memory_id,
                            *scope,
                        ),
                    )
                else:
                    cursor.execute(
                        f"""
                        UPDATE {SCHEMA}.long_term_memories
                        SET status='SUPERSEDED', updated_at=%s
                        WHERE id=%s AND tenant_id=%s AND user_id=%s AND agent_id=%s
                          AND status='ACTIVE'
                        RETURNING *
                        """,
                        (now, memory_id, *scope),
                    )
                updated = cursor.fetchone()
                if updated is None:
                    return None
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.memory_audit_events
                    (tenant_id,user_id,agent_id,memory_id,actor,action,reason,created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (*scope, memory_id, actor, f"FEEDBACK_{action}", reason, now),
                )
                return _memory(updated)

        return self._run(operation)


def _health(connection) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        return cursor.fetchone()[0] == 1


def _job_parameters(job: ExtractionJob) -> tuple[object, ...]:
    return (
        job.extraction_id,
        *job.scope,
        job.conversation_id,
        job.turn_id,
        job.user_message,
        job.assistant_message,
        job.occurred_at,
        job.idempotency_hash,
        job.request_fingerprint,
        job.status,
        job.attempt_count,
        job.max_attempts,
        job.next_attempt_at,
        job.lease_until,
        job.written_count,
        job.rejected_count,
        job.error_code,
        job.created_at,
        job.updated_at,
    )


def _job(row: dict[str, object]) -> ExtractionJob:
    return ExtractionJob(
        extraction_id=str(row["id"]),
        scope=(str(row["tenant_id"]), str(row["user_id"]), str(row["agent_id"])),
        conversation_id=str(row["conversation_id"]),
        turn_id=str(row["turn_id"]),
        user_message=str(row["user_message"]),
        assistant_message=str(row["assistant_message"]),
        occurred_at=row["occurred_at"],
        idempotency_hash=str(row["idempotency_hash"]),
        request_fingerprint=str(row["request_fingerprint"]),
        status=str(row["status"]),
        attempt_count=int(row["attempt_count"]),
        max_attempts=int(row["max_attempts"]),
        next_attempt_at=row["next_attempt_at"],
        lease_until=row["lease_until"],
        written_count=int(row["written_count"]),
        rejected_count=int(row["rejected_count"]),
        error_code=str(row["error_code"]) if row["error_code"] is not None else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _memory(row: dict[str, object]) -> LongTermMemoryRecord:
    return LongTermMemoryRecord(
        memory_id=str(row["id"]),
        scope=(str(row["tenant_id"]), str(row["user_id"]), str(row["agent_id"])),
        memory_type=str(row["memory_type"]),
        content=str(row["content"]),
        content_hash=str(row["content_hash"]),
        confidence=float(row["confidence"]),
        source_type=str(row["source_type"]),
        source_ref=str(row["source_ref"]),
        status=str(row["status"]),
        last_confirmed_at=row["last_confirmed_at"],
        expires_at=row["expires_at"],
        deleted_at=row["deleted_at"],
        deletion_reason=str(row["delete_reason"]) if row["delete_reason"] else None,
        deletion_actor=str(row["deleted_by"]) if row["deleted_by"] else None,
    )
