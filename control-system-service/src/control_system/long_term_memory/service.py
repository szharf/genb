import hashlib
import json

from ..component_config import RuntimeConfigUnavailable
from ..errors import (
    LongTermIdempotencyProblem,
    LongTermMemoryNotFoundProblem,
    LongTermMemoryUnavailableProblem,
)
from ..identity import InvocationIdentity
from ..short_term_memory.redaction import redact_sensitive_content
from ..telemetry import MetricsRegistry
from .config import LongTermMemoryConfigProvider, MEMORY_TYPES
from .extraction import MemoryExtractionModel
from .models import (
    MEMORY_SOURCE_TYPES,
    ExtractionJob,
    ExtractionRequest,
    LongTermMemoryRecord,
    MemoryScope,
)
from .repository import (
    ExtractionIdempotencyConflict,
    LongTermMemoryRepository,
    LongTermRepositoryUnavailable,
)
from .worker import ExtractionWorker


class LongTermMemoryService:
    def __init__(
        self,
        repository: LongTermMemoryRepository,
        *,
        config_provider: LongTermMemoryConfigProvider,
        extraction_model: MemoryExtractionModel,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._config_provider = config_provider
        self._metrics = metrics or MetricsRegistry()
        self.worker = ExtractionWorker(
            repository,
            extraction_model=extraction_model,
            metrics=self._metrics,
        )

    @staticmethod
    def scope(identity: InvocationIdentity) -> MemoryScope:
        return identity.tenant_id, identity.user_id, identity.agent_id

    def _config(self, identity: InvocationIdentity):
        try:
            config = self._config_provider.get(identity)
        except RuntimeConfigUnavailable as error:
            raise LongTermMemoryUnavailableProblem(identity.request_id) from error
        config_id = identity.config_version_for("LONG_TERM_MEMORY")
        if config_id is not None:
            self._metrics.set(
                "component_config_active_version",
                config_id,
                {"component": "LONG_TERM_MEMORY"},
            )
        return config

    async def request_extraction(
        self,
        identity: InvocationIdentity,
        request: ExtractionRequest,
        idempotency_key: str,
    ) -> tuple[ExtractionJob, bool]:
        config = self._config(identity)
        if not config.auto_extraction_enabled:
            raise LongTermMemoryUnavailableProblem(identity.request_id)
        config_version_id = identity.config_version_for("LONG_TERM_MEMORY")
        if config_version_id is None:
            raise LongTermMemoryUnavailableProblem(identity.request_id)
        request_payload = {
            "turnId": request.turn_id,
            "userMessage": request.user_message,
            "assistantMessage": request.assistant_message,
            "occurredAt": request.occurred_at.isoformat(),
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                request_payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        idempotency_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
        try:
            job, duplicate = await self._repository.create_extraction(
                self.scope(identity),
                turn_id=request.turn_id,
                user_message=redact_sensitive_content(request.user_message),
                assistant_message=redact_sensitive_content(request.assistant_message),
                occurred_at=request.occurred_at,
                idempotency_hash=idempotency_hash,
                request_fingerprint=fingerprint,
                config_version_id=config_version_id,
                config=config,
            )
            self._metrics.increment(
                "extraction_jobs_total",
                {"result": "duplicate" if duplicate else "accepted"},
            )
            return job, duplicate
        except ExtractionIdempotencyConflict as error:
            raise LongTermIdempotencyProblem(identity.request_id) from error
        except LongTermRepositoryUnavailable as error:
            raise LongTermMemoryUnavailableProblem(identity.request_id) from error

    async def get_extraction(
        self, identity: InvocationIdentity, extraction_id: str
    ) -> ExtractionJob:
        try:
            job = await self._repository.get_extraction(
                self.scope(identity), extraction_id
            )
        except LongTermRepositoryUnavailable as error:
            raise LongTermMemoryUnavailableProblem(identity.request_id) from error
        if job is None:
            raise LongTermMemoryNotFoundProblem(identity.request_id)
        return job

    async def search(
        self,
        identity: InvocationIdentity,
        *,
        query: str,
        requested_types: list[str] | None,
        requested_source_types: list[str] | None,
        requested_top_k: int | None,
    ) -> tuple[list[LongTermMemoryRecord], int]:
        config = self._config(identity)
        types = (
            frozenset(requested_types)
            if requested_types
            else config.enabled_types
        )
        types = frozenset(types & config.enabled_types & MEMORY_TYPES)
        source_types = frozenset(requested_source_types or MEMORY_SOURCE_TYPES)
        source_types = frozenset(source_types & MEMORY_SOURCE_TYPES)
        limit = min(requested_top_k or config.top_k, config.max_top_k)
        try:
            items = await self._repository.search(
                self.scope(identity),
                query=query,
                types=types,
                source_types=source_types,
                limit=limit,
            )
        except LongTermRepositoryUnavailable as error:
            raise LongTermMemoryUnavailableProblem(identity.request_id) from error
        self._metrics.increment("long_term_search_total", {"result": "success"})
        self._metrics.increment("long_term_search_hits", amount=len(items))
        return items, limit

    async def delete_memory(
        self,
        identity: InvocationIdentity,
        memory_id: str,
        *,
        reason: str,
    ) -> bool:
        try:
            deleted = await self._repository.delete_memory(
                self.scope(identity),
                memory_id,
                actor=f"agent:{identity.agent_id}",
                reason=reason,
                request_id=identity.request_id,
            )
        except LongTermRepositoryUnavailable as error:
            raise LongTermMemoryUnavailableProblem(identity.request_id) from error
        self._metrics.increment(
            "long_term_delete_total",
            {"result": "deleted" if deleted else "not_found"},
        )
        return deleted
