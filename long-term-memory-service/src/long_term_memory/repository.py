import hashlib
import unicodedata
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from .extraction import ExtractionCandidate
from .models import ExtractionJob, LongTermMemoryRecord, MemoryScope


class ExtractionIdempotencyConflict(Exception):
    pass


class ConversationMemoryRepositoryUnavailable(Exception):
    pass


class ConversationMemoryRepository(Protocol):
    def health(self) -> bool: ...

    def create_extraction(self, job: ExtractionJob) -> tuple[ExtractionJob, bool]: ...

    def get_extraction(
        self, scope: MemoryScope, extraction_id: str
    ) -> ExtractionJob | None: ...

    def search(
        self,
        scope: MemoryScope,
        *,
        query: str,
        types: frozenset[str] | None,
        source_types: frozenset[str],
        limit: int,
    ) -> list[LongTermMemoryRecord]: ...

    def get_extraction_by_id(self, extraction_id: str) -> ExtractionJob | None: ...

    def claim_extraction(
        self, extraction_id: str, *, lease_seconds: int
    ) -> ExtractionJob | None: ...

    def complete_extraction(
        self,
        extraction_id: str,
        *,
        status: str,
        written_count: int,
        rejected_count: int,
        error_code: str | None,
    ) -> None: ...

    def retry_extraction(
        self,
        extraction_id: str,
        *,
        error_code: str,
        retry_after_seconds: int,
    ) -> str: ...

    def upsert_memory(
        self,
        scope: MemoryScope,
        candidate: ExtractionCandidate,
        *,
        source_ref: str,
        retention_days: int,
    ) -> LongTermMemoryRecord: ...

    def delete_memory(
        self,
        scope: MemoryScope,
        memory_id: str,
        *,
        actor: str,
        reason: str,
    ) -> bool: ...

    def correct_memory(
        self,
        scope: MemoryScope,
        memory_id: str,
        *,
        content: str,
        actor: str,
        reason: str,
        retention_days: int,
    ) -> LongTermMemoryRecord | None: ...

    def record_feedback(
        self,
        scope: MemoryScope,
        memory_id: str,
        *,
        action: str,
        actor: str,
        reason: str,
        retention_days: int,
    ) -> LongTermMemoryRecord | None: ...


class InMemoryConversationMemoryRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, ExtractionJob] = {}
        self._idempotency: dict[tuple[MemoryScope, str], str] = {}
        self._memories: dict[str, LongTermMemoryRecord] = {}
        self._audit_events: list[dict[str, object]] = []

    def health(self) -> bool:
        return True

    def create_extraction(self, job: ExtractionJob) -> tuple[ExtractionJob, bool]:
        key = (job.scope, job.idempotency_hash)
        existing_id = self._idempotency.get(key)
        if existing_id is not None:
            existing = self._jobs[existing_id]
            if existing.request_fingerprint != job.request_fingerprint:
                raise ExtractionIdempotencyConflict
            return existing, True
        self._jobs[job.extraction_id] = job
        self._idempotency[key] = job.extraction_id
        return job, False

    def get_extraction(
        self, scope: MemoryScope, extraction_id: str
    ) -> ExtractionJob | None:
        job = self._jobs.get(extraction_id)
        return job if job is not None and job.scope == scope else None

    def get_extraction_by_id(self, extraction_id: str) -> ExtractionJob | None:
        return self._jobs.get(extraction_id)

    def claim_extraction(
        self, extraction_id: str, *, lease_seconds: int
    ) -> ExtractionJob | None:
        now = datetime.now(UTC)
        job = self._jobs.get(extraction_id)
        if job is None or job.attempt_count >= job.max_attempts:
            return None
        eligible = job.status == "PENDING" and job.next_attempt_at <= now
        eligible = eligible or (
            job.status == "RUNNING"
            and job.lease_until is not None
            and job.lease_until <= now
        )
        if not eligible:
            return None
        claimed = replace(
            job,
            status="RUNNING",
            attempt_count=job.attempt_count + 1,
            lease_until=now + timedelta(seconds=lease_seconds),
            updated_at=now,
        )
        self._jobs[extraction_id] = claimed
        return claimed

    def complete_extraction(
        self,
        extraction_id: str,
        *,
        status: str,
        written_count: int,
        rejected_count: int,
        error_code: str | None,
    ) -> None:
        job = self._jobs[extraction_id]
        self._jobs[extraction_id] = replace(
            job,
            status=status,
            written_count=written_count,
            rejected_count=rejected_count,
            error_code=error_code,
            lease_until=None,
            updated_at=datetime.now(UTC),
        )

    def retry_extraction(
        self,
        extraction_id: str,
        *,
        error_code: str,
        retry_after_seconds: int,
    ) -> str:
        job = self._jobs[extraction_id]
        now = datetime.now(UTC)
        status = "DEAD" if job.attempt_count >= job.max_attempts else "PENDING"
        self._jobs[extraction_id] = replace(
            job,
            status=status,
            error_code=error_code,
            next_attempt_at=now + timedelta(seconds=retry_after_seconds),
            lease_until=None,
            updated_at=now,
        )
        return status

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
        existing = next(
            (
                memory
                for memory in self._memories.values()
                if memory.scope == scope
                and memory.memory_type == candidate.memory_type
                and memory.content_hash == content_hash
                and memory.status == "ACTIVE"
            ),
            None,
        )
        if existing is not None:
            updated = replace(
                existing,
                confidence=max(existing.confidence, candidate.confidence),
                source_ref=source_ref,
                last_confirmed_at=now,
                expires_at=now + timedelta(days=retention_days),
            )
            self._memories[existing.memory_id] = updated
            return updated
        memory = LongTermMemoryRecord(
            memory_id=f"mem_{uuid4().hex}",
            scope=scope,
            memory_type=candidate.memory_type,
            content=candidate.content,
            content_hash=content_hash,
            confidence=candidate.confidence,
            source_type="CONVERSATION",
            source_ref=source_ref,
            status="ACTIVE",
            last_confirmed_at=now,
            expires_at=now + timedelta(days=retention_days),
            deleted_at=None,
            deletion_reason=None,
            deletion_actor=None,
        )
        self._memories[memory.memory_id] = memory
        return memory

    def delete_memory(
        self,
        scope: MemoryScope,
        memory_id: str,
        *,
        actor: str,
        reason: str,
    ) -> bool:
        memory = self._memories.get(memory_id)
        if memory is None or memory.scope != scope or memory.status != "ACTIVE":
            return False
        self._memories[memory_id] = replace(
            memory,
            status="DELETED",
            deleted_at=datetime.now(UTC),
            deletion_reason=reason,
            deletion_actor=actor,
        )
        self._audit_events.append(
            {
                "scope": scope,
                "memory_id": memory_id,
                "actor": actor,
                "action": "DELETE",
                "reason": reason,
                "created_at": datetime.now(UTC),
            }
        )
        return True

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
        original = self._memories.get(memory_id)
        if original is None or original.scope != scope or original.status != "ACTIVE":
            return None
        now = datetime.now(UTC)
        self._memories[memory_id] = replace(original, status="SUPERSEDED")
        corrected = self.upsert_memory(
            scope,
            ExtractionCandidate(
                memory_type=original.memory_type,
                content=content,
                confidence=original.confidence,
            ),
            source_ref=f"correction:{memory_id}",
            retention_days=retention_days,
        )
        self._audit_events.append(
            {
                "scope": scope,
                "memory_id": memory_id,
                "replacement_memory_id": corrected.memory_id,
                "actor": actor,
                "action": "CORRECT",
                "reason": reason,
                "created_at": now,
            }
        )
        return corrected

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
        memory = self._memories.get(memory_id)
        if memory is None or memory.scope != scope or memory.status != "ACTIVE":
            return None
        now = datetime.now(UTC)
        if action == "CONFIRM":
            updated = replace(
                memory,
                confidence=min(1.0, memory.confidence + 0.05),
                last_confirmed_at=now,
                expires_at=now + timedelta(days=retention_days),
            )
        else:
            updated = replace(memory, status="SUPERSEDED")
        self._memories[memory_id] = updated
        self._audit_events.append(
            {
                "scope": scope,
                "memory_id": memory_id,
                "actor": actor,
                "action": f"FEEDBACK_{action}",
                "reason": reason,
                "created_at": now,
            }
        )
        return updated

    def search(
        self,
        scope: MemoryScope,
        *,
        query: str,
        types: frozenset[str] | None,
        source_types: frozenset[str],
        limit: int,
    ) -> list[LongTermMemoryRecord]:
        query_text = query.casefold().strip()
        matches = [
            memory
            for memory in self._memories.values()
            if memory.scope == scope
            and memory.status == "ACTIVE"
            and memory.source_type in source_types
            and (types is None or memory.memory_type in types)
            and (not query_text or query_text in memory.content.casefold())
        ]
        matches.sort(key=lambda memory: memory.last_confirmed_at, reverse=True)
        return matches[:limit]
