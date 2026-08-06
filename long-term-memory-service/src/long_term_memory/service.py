import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from .extraction import (
    InvalidExtractionOutput,
    MemoryExtractionModel,
    RetryableExtractionError,
)
from .identity import InvocationIdentity
from .knowledge_base import (
    KnowledgeBaseAccessRevoked,
    KnowledgeBaseAdapter,
    KnowledgeBasePermissionDenied,
    KnowledgeBaseTimeout,
    KnowledgeBaseUnavailable,
    UnavailableKnowledgeBaseAdapter,
)
from .models import (
    ExtractionJob,
    ExtractionRequest,
    LongTermMemoryRecord,
    MemoryScope,
    SearchRequest,
)
from .repository import (
    ConversationMemoryRepository,
    ExtractionIdempotencyConflict,
)


_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")


class LongTermMemoryIdempotencyProblem(Exception):
    pass


class LongTermMemorySourceUnavailable(Exception):
    pass


class LongTermMemorySourceForbidden(Exception):
    pass


@dataclass(frozen=True)
class SearchOutcome:
    items: tuple[LongTermMemoryRecord, ...]
    degraded_sources: tuple[str, ...]


def _redact(value: str) -> str:
    return _PHONE.sub("[REDACTED_PHONE]", value)


class LongTermMemoryService:
    def __init__(
        self,
        repository: ConversationMemoryRepository,
        *,
        extraction_model: MemoryExtractionModel | None = None,
        knowledge_base_adapter: KnowledgeBaseAdapter | None = None,
        confidence_threshold: float = 0.8,
        retention_days: int = 180,
        max_attempts: int = 3,
    ) -> None:
        self._repository = repository
        self._extraction_model = extraction_model
        self._knowledge_base_adapter = (
            knowledge_base_adapter or UnavailableKnowledgeBaseAdapter()
        )
        self._confidence_threshold = confidence_threshold
        self._retention_days = retention_days
        self._max_attempts = max_attempts

    @staticmethod
    def scope(identity: InvocationIdentity) -> MemoryScope:
        return identity.tenant_id, identity.user_id, identity.agent_id

    def request_extraction(
        self,
        identity: InvocationIdentity,
        request: ExtractionRequest,
        idempotency_key: str,
    ) -> tuple[ExtractionJob, bool]:
        request_payload = request.model_dump(mode="json", by_alias=True)
        fingerprint = hashlib.sha256(
            json.dumps(
                request_payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        now = datetime.now(UTC)
        job = ExtractionJob(
            extraction_id=str(uuid4()),
            scope=self.scope(identity),
            conversation_id=request.conversation_id,
            turn_id=request.turn_id,
            user_message=_redact(request.user_message),
            assistant_message=_redact(request.assistant_message),
            occurred_at=request.occurred_at,
            idempotency_hash=hashlib.sha256(idempotency_key.encode()).hexdigest(),
            request_fingerprint=fingerprint,
            status="PENDING",
            attempt_count=0,
            max_attempts=self._max_attempts,
            next_attempt_at=now,
            lease_until=None,
            written_count=0,
            rejected_count=0,
            error_code=None,
            created_at=now,
            updated_at=now,
        )
        try:
            return self._repository.create_extraction(job)
        except ExtractionIdempotencyConflict as error:
            raise LongTermMemoryIdempotencyProblem from error

    def get_extraction(
        self, identity: InvocationIdentity, extraction_id: str
    ) -> ExtractionJob | None:
        return self._repository.get_extraction(self.scope(identity), extraction_id)

    def search(
        self, identity: InvocationIdentity, request: SearchRequest
    ) -> SearchOutcome:
        requested_sources = frozenset(request.source_types)
        requested_types = frozenset(request.types) if request.types else None
        items: list[LongTermMemoryRecord] = []
        degraded: list[str] = []
        if "CONVERSATION" in requested_sources:
            items.extend(
                self._repository.search(
                    self.scope(identity),
                    query=request.query,
                    types=requested_types,
                    source_types=frozenset({"CONVERSATION"}),
                    limit=request.top_k,
                )
            )
        if "KNOWLEDGE_BASE" in requested_sources:
            try:
                items.extend(
                    self._knowledge_base_adapter.search(
                        tenant_id=identity.tenant_id,
                        agent_id=identity.agent_id,
                        user_id=identity.user_id,
                        query=request.query,
                        types=requested_types,
                        limit=request.top_k,
                    )
                )
            except (KnowledgeBaseUnavailable, KnowledgeBaseTimeout) as error:
                if "CONVERSATION" not in requested_sources:
                    raise LongTermMemorySourceUnavailable from error
                degraded.append("KNOWLEDGE_BASE")
            except (
                KnowledgeBasePermissionDenied,
                KnowledgeBaseAccessRevoked,
            ) as error:
                raise LongTermMemorySourceForbidden from error
        items.sort(key=lambda item: item.last_confirmed_at, reverse=True)
        return SearchOutcome(tuple(items[: request.top_k]), tuple(degraded))

    def process_extraction(self, extraction_id: str) -> None:
        if self._extraction_model is None:
            return
        job = self._repository.claim_extraction(extraction_id, lease_seconds=60)
        if job is None:
            return
        try:
            result = self._extraction_model.extract(
                user_message=job.user_message,
                assistant_message=job.assistant_message,
            )
        except RetryableExtractionError:
            self._repository.retry_extraction(
                extraction_id,
                error_code="RUNTIME_UNAVAILABLE",
                retry_after_seconds=5,
            )
            return
        except InvalidExtractionOutput:
            self._repository.complete_extraction(
                extraction_id,
                status="FAILED",
                written_count=0,
                rejected_count=0,
                error_code="INVALID_EXTRACTION_OUTPUT",
            )
            return
        written = 0
        rejected = 0
        for candidate in result.candidates:
            if not self._candidate_is_safe(candidate.content, candidate.confidence):
                rejected += 1
                continue
            self._repository.upsert_memory(
                job.scope,
                candidate,
                source_ref=job.turn_id,
                retention_days=self._retention_days,
            )
            written += 1
        self._repository.complete_extraction(
            extraction_id,
            status="SUCCEEDED",
            written_count=written,
            rejected_count=rejected,
            error_code=None,
        )

    def delete_memory(
        self,
        identity: InvocationIdentity,
        memory_id: str,
        *,
        reason: str,
    ) -> bool:
        return self._repository.delete_memory(
            self.scope(identity),
            memory_id,
            actor=f"user:{identity.user_id}",
            reason=reason,
        )

    def correct_memory(
        self,
        identity: InvocationIdentity,
        memory_id: str,
        *,
        content: str,
        reason: str,
    ) -> LongTermMemoryRecord | None:
        if not self._candidate_is_safe(content, 1.0):
            return None
        return self._repository.correct_memory(
            self.scope(identity),
            memory_id,
            content=content,
            actor=f"user:{identity.user_id}",
            reason=reason,
            retention_days=self._retention_days,
        )

    def record_feedback(
        self,
        identity: InvocationIdentity,
        memory_id: str,
        *,
        action: str,
        reason: str,
    ) -> LongTermMemoryRecord | None:
        return self._repository.record_feedback(
            self.scope(identity),
            memory_id,
            action=action,
            actor=f"user:{identity.user_id}",
            reason=reason,
            retention_days=self._retention_days,
        )

    def _candidate_is_safe(self, content: str, confidence: float) -> bool:
        if not content.strip() or len(content) > 4000:
            return False
        if confidence < self._confidence_threshold:
            return False
        normalized = content.casefold()
        forbidden = ("password", "密码", "verification code", "验证码", "api key", "token")
        return not any(marker in normalized for marker in forbidden)
