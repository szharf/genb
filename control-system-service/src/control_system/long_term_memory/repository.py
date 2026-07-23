import hashlib
import re
import unicodedata
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from .config import LongTermMemoryRuntimeConfig
from .extraction import ExtractionCandidate
from .models import ExtractionJob, LongTermMemoryRecord, MemoryScope


class ExtractionIdempotencyConflict(Exception):
    pass


class LongTermRepositoryUnavailable(Exception):
    pass


class LongTermMemoryRepository(Protocol):
    async def health(self) -> bool: ...

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
    ) -> tuple[ExtractionJob, bool]: ...

    async def get_extraction(
        self, scope: MemoryScope, extraction_id: str
    ) -> ExtractionJob | None: ...

    async def claim_extraction(self, extraction_id: str) -> ExtractionJob | None: ...

    async def next_pending_extraction_id(self) -> str | None: ...

    async def pending_extraction_stats(self) -> tuple[int, float]: ...

    async def retry_extraction(
        self, extraction_id: str, *, error_code: str, retry_after_seconds: int
    ) -> str: ...

    async def complete_extraction(
        self,
        extraction_id: str,
        *,
        status: str,
        written_count: int,
        rejected_count: int,
        model: str | None,
        error_code: str | None,
    ) -> None: ...

    async def upsert_memory(
        self,
        scope: MemoryScope,
        candidate: ExtractionCandidate,
        *,
        retention_days: int,
        source_ref: str,
    ) -> LongTermMemoryRecord: ...

    async def search(
        self,
        scope: MemoryScope,
        *,
        query: str,
        types: frozenset[str],
        limit: int,
    ) -> list[LongTermMemoryRecord]: ...

    async def delete_memory(
        self,
        scope: MemoryScope,
        memory_id: str,
        *,
        actor: str,
        reason: str,
        request_id: str | None,
    ) -> bool: ...


class InMemoryLongTermMemoryRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, ExtractionJob] = {}
        self._idempotency: dict[tuple[MemoryScope, str], tuple[str, str]] = {}
        self._memories: dict[str, LongTermMemoryRecord] = {}

    async def health(self) -> bool:
        return True

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
        key = (scope, idempotency_hash)
        previous = self._idempotency.get(key)
        if previous:
            previous_fingerprint, extraction_id = previous
            if previous_fingerprint != request_fingerprint:
                raise ExtractionIdempotencyConflict
            return self._jobs[extraction_id], True
        now = datetime.now(UTC)
        extraction_id = f"ext_{uuid4().hex}"
        job = ExtractionJob(
            extraction_id=extraction_id,
            scope=scope,
            turn_id=turn_id,
            user_message=user_message,
            assistant_message=assistant_message,
            occurred_at=occurred_at,
            idempotency_hash=idempotency_hash,
            request_fingerprint=request_fingerprint,
            config_version_id=config_version_id,
            config=config,
            status="PENDING",
            attempt_count=0,
            written_count=0,
            rejected_count=0,
            model=None,
            error_code=None,
            next_attempt_at=now,
            lease_until=None,
            created_at=now,
            updated_at=now,
        )
        self._jobs[extraction_id] = job
        self._idempotency[key] = (request_fingerprint, extraction_id)
        return job, False

    async def get_extraction(
        self, scope: MemoryScope, extraction_id: str
    ) -> ExtractionJob | None:
        job = self._jobs.get(extraction_id)
        return job if job and job.scope == scope else None

    async def claim_extraction(self, extraction_id: str) -> ExtractionJob | None:
        job = self._jobs.get(extraction_id)
        now = datetime.now(UTC)
        if job is None or (
            job.status not in {"PENDING", "RUNNING"}
            or job.next_attempt_at > now
            or (job.status == "RUNNING" and job.lease_until and job.lease_until > now)
        ):
            return None
        if job.attempt_count >= job.config.max_attempts:
            dead = replace(job, status="DEAD", updated_at=datetime.now(UTC))
            self._jobs[extraction_id] = dead
            return None
        claimed = replace(
            job,
            status="RUNNING",
            attempt_count=job.attempt_count + 1,
            lease_until=now + timedelta(seconds=60),
            updated_at=now,
        )
        self._jobs[extraction_id] = claimed
        return claimed

    async def next_pending_extraction_id(self) -> str | None:
        now = datetime.now(UTC)
        eligible = [
            job
            for job in self._jobs.values()
            if job.next_attempt_at <= now
            and (
                job.status == "PENDING"
                or job.status == "RUNNING"
                and job.lease_until is not None
                and job.lease_until <= now
            )
        ]
        return min(eligible, key=lambda job: job.created_at).extraction_id if eligible else None

    async def pending_extraction_stats(self) -> tuple[int, float]:
        now = datetime.now(UTC)
        pending = [
            job
            for job in self._jobs.values()
            if job.status == "PENDING"
            or job.status == "RUNNING"
            and job.lease_until is not None
            and job.lease_until <= now
        ]
        if not pending:
            return 0, 0.0
        oldest = min(job.created_at for job in pending)
        return len(pending), max(0.0, (now - oldest).total_seconds())

    async def retry_extraction(
        self, extraction_id: str, *, error_code: str, retry_after_seconds: int
    ) -> str:
        job = self._jobs[extraction_id]
        status = "DEAD" if job.attempt_count >= job.config.max_attempts else "PENDING"
        now = datetime.now(UTC)
        self._jobs[extraction_id] = replace(
            job,
            status=status,
            error_code=error_code,
            lease_until=None,
            next_attempt_at=now + timedelta(seconds=retry_after_seconds),
            updated_at=now,
        )
        return status

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
        job = self._jobs[extraction_id]
        self._jobs[extraction_id] = replace(
            job,
            status=status,
            written_count=written_count,
            rejected_count=rejected_count,
            model=model,
            error_code=error_code,
            lease_until=None,
            updated_at=datetime.now(UTC),
        )

    async def upsert_memory(
        self,
        scope: MemoryScope,
        candidate: ExtractionCandidate,
        *,
        retention_days: int,
        source_ref: str,
    ) -> LongTermMemoryRecord:
        normalized = normalize_content(candidate.content)
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
        if existing:
            updated = replace(
                existing,
                confidence=max(existing.confidence, candidate.confidence),
                last_confirmed_at=now,
                expires_at=now + timedelta(days=retention_days),
            )
            self._memories[existing.memory_id] = updated
            return updated
        memory = LongTermMemoryRecord(
            memory_id=f"mem_{uuid4().hex}",
            scope=scope,
            memory_type=candidate.memory_type,
            content=normalized,
            content_hash=content_hash,
            confidence=candidate.confidence,
            source_ref=source_ref,
            status="ACTIVE",
            first_seen_at=now,
            last_confirmed_at=now,
            last_accessed_at=None,
            expires_at=now + timedelta(days=retention_days),
        )
        self._memories[memory.memory_id] = memory
        return memory

    async def search(
        self,
        scope: MemoryScope,
        *,
        query: str,
        types: frozenset[str],
        limit: int,
    ) -> list[LongTermMemoryRecord]:
        now = datetime.now(UTC)
        normalized_query = normalize_content(query)
        terms = [term for term in re.split(r"\s+", normalized_query) if term]
        candidates = [
            memory
            for memory in self._memories.values()
            if memory.scope == scope
            and memory.status == "ACTIVE"
            and memory.expires_at > now
            and memory.memory_type in types
        ]

        def rank(memory: LongTermMemoryRecord):
            hit = int(
                not terms
                or normalized_query in memory.content
                or any(term in memory.content for term in terms)
            )
            return hit, memory.confidence, memory.last_confirmed_at

        selected = sorted(candidates, key=rank, reverse=True)[:limit]
        for memory in selected:
            self._memories[memory.memory_id] = replace(
                memory, last_accessed_at=now
            )
        return selected

    async def delete_memory(
        self,
        scope: MemoryScope,
        memory_id: str,
        *,
        actor: str,
        reason: str,
        request_id: str | None,
    ) -> bool:
        del actor, reason, request_id
        memory = self._memories.get(memory_id)
        if memory is None or memory.scope != scope or memory.status == "DELETED":
            return False
        self._memories[memory_id] = replace(memory, status="DELETED")
        return True


def normalize_content(content: str) -> str:
    normalized = unicodedata.normalize("NFKC", content).strip()
    return re.sub(r"\s+", " ", normalized)
