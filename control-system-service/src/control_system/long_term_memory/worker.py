import asyncio
from uuid import uuid4

from ..short_term_memory.redaction import contains_sensitive_content
from ..telemetry import MetricsRegistry
from .config import MEMORY_TYPES
from .extraction import (
    ExtractionModelRequest,
    InvalidExtractionOutput,
    MemoryExtractionModel,
    RetryableExtractionError,
)
from .repository import LongTermMemoryRepository


class ExtractionWorker:
    def __init__(
        self,
        repository: LongTermMemoryRepository,
        *,
        extraction_model: MemoryExtractionModel,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._model = extraction_model
        self._metrics = metrics or MetricsRegistry()

    async def process(self, extraction_id: str, request_id: str, trace_parent: str | None) -> str:
        job = await self._repository.claim_extraction(extraction_id)
        if job is None:
            return "NOT_CLAIMED"
        try:
            result = await self._model.extract(
                ExtractionModelRequest(
                    user_message=job.user_message,
                    assistant_message=job.assistant_message,
                    model_alias=job.config.model_alias,
                    request_id=request_id,
                    trace_parent=trace_parent,
                )
            )
            written = 0
            rejected = 0
            for candidate in result.candidates:
                if not (
                    candidate.action == "UPSERT"
                    and candidate.memory_type in MEMORY_TYPES
                    and candidate.memory_type in job.config.enabled_types
                    and candidate.confidence >= job.config.confidence_threshold
                    and candidate.content.strip()
                    and len(candidate.content) <= 4000
                    and not contains_sensitive_content(candidate.content)
                ):
                    rejected += 1
                    continue
                await self._repository.upsert_memory(
                    job.scope,
                    candidate,
                    retention_days=job.config.retention_days,
                    source_ref=job.turn_id,
                )
                written += 1
            status = "SUCCEEDED" if written else "NO_WRITE"
            await self._repository.complete_extraction(
                extraction_id,
                status=status,
                written_count=written,
                rejected_count=rejected,
                model=result.model,
                error_code=None,
            )
            self._metrics.increment("extraction_jobs", {"status": status.lower()})
            return status
        except RetryableExtractionError:
            retry_delay = min(300, 2 ** job.attempt_count)
            status = await self._repository.retry_extraction(
                extraction_id,
                error_code="INFERENCE_UNAVAILABLE",
                retry_after_seconds=retry_delay,
            )
            self._metrics.increment("extraction_jobs", {"status": status.lower()})
            return status
        except InvalidExtractionOutput:
            await self._repository.complete_extraction(
                extraction_id,
                status="NO_WRITE",
                written_count=0,
                rejected_count=0,
                model=None,
                error_code="INVALID_MODEL_OUTPUT",
            )
            self._metrics.increment("extraction_jobs", {"status": "no_write"})
            return "NO_WRITE"
        except Exception:
            await self._repository.complete_extraction(
                extraction_id,
                status="FAILED",
                written_count=0,
                rejected_count=0,
                model=None,
                error_code="INTERNAL_ERROR",
            )
            self._metrics.increment("extraction_jobs", {"status": "failed"})
            return "FAILED"


class ExtractionWorkerRunner:
    def __init__(
        self,
        worker: ExtractionWorker,
        repository: LongTermMemoryRepository,
        *,
        poll_seconds: float = 1.0,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._worker = worker
        self._repository = repository
        self._poll_seconds = poll_seconds
        self._metrics = metrics or MetricsRegistry()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="long-term-extraction-worker")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        while True:
            await self.refresh_metrics()
            extraction_id = await self._repository.next_pending_extraction_id()
            if extraction_id is None:
                await asyncio.sleep(self._poll_seconds)
                continue
            await self._worker.process(
                extraction_id,
                request_id=f"worker-{uuid4().hex}",
                trace_parent=None,
            )

    async def refresh_metrics(self) -> None:
        depth, oldest_age = await self._repository.pending_extraction_stats()
        self._metrics.set("long_term_extraction_queue_depth", depth)
        self._metrics.set("long_term_extraction_oldest_age_seconds", oldest_age)
