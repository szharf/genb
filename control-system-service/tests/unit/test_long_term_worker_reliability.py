from datetime import UTC, datetime, timedelta

import pytest

from control_system.long_term_memory.config import LongTermMemoryRuntimeConfig
from control_system.long_term_memory.extraction import (
    InvalidExtractionOutput,
    RetryableExtractionError,
)
from control_system.long_term_memory.repository import InMemoryLongTermMemoryRepository
from control_system.long_term_memory.worker import ExtractionWorker


class FailingModel:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def extract(self, request):
        del request
        raise self.error


async def _job(repository, max_attempts=2):
    config = LongTermMemoryRuntimeConfig(
        enabled_types=frozenset({"USER_PREFERENCE"}),
        auto_extraction_enabled=True,
        confidence_threshold=0.8,
        retention_days=30,
        top_k=5,
        max_top_k=10,
        model_alias="memory-test",
        max_attempts=max_attempts,
    )
    job, _ = await repository.create_extraction(
        ("tenant-a", "user-a", "agent-a"),
        turn_id="turn-1",
        user_message="I prefer tea",
        assistant_message="Understood",
        occurred_at=datetime.now(UTC),
        idempotency_hash="a" * 64,
        request_fingerprint="b" * 64,
        config_version_id=1,
        config=config,
    )
    return job


@pytest.mark.asyncio
async def test_retryable_failure_is_rescheduled_then_dead() -> None:
    repository = InMemoryLongTermMemoryRepository()
    job = await _job(repository)
    worker = ExtractionWorker(repository, extraction_model=FailingModel(RetryableExtractionError()))

    assert await worker.process(job.extraction_id, "request-1", None) == "PENDING"
    pending = await repository.get_extraction(job.scope, job.extraction_id)
    assert pending and pending.attempt_count == 1 and pending.error_code == "INFERENCE_UNAVAILABLE"
    repository._jobs[job.extraction_id] = pending.__class__(
        **{**pending.__dict__, "next_attempt_at": datetime.now(UTC) - timedelta(seconds=1)}
    )
    assert await worker.process(job.extraction_id, "request-2", None) == "DEAD"


@pytest.mark.asyncio
async def test_invalid_structured_output_is_no_write_without_retry() -> None:
    repository = InMemoryLongTermMemoryRepository()
    job = await _job(repository)
    worker = ExtractionWorker(repository, extraction_model=FailingModel(InvalidExtractionOutput()))

    assert await worker.process(job.extraction_id, "request-1", None) == "NO_WRITE"
    completed = await repository.get_extraction(job.scope, job.extraction_id)
    assert completed and completed.attempt_count == 1
    assert completed.error_code == "INVALID_MODEL_OUTPUT"
