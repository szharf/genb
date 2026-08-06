from datetime import UTC, datetime

from long_term_memory.identity import InvocationIdentity
from long_term_memory.extraction import RetryableExtractionError
from long_term_memory.models import ExtractionRequest
from long_term_memory.repository import InMemoryConversationMemoryRepository
from long_term_memory.service import LongTermMemoryService


def test_pending_extraction_cannot_be_claimed_twice_while_lease_is_active() -> None:
    repository = InMemoryConversationMemoryRepository()
    service = LongTermMemoryService(repository)
    identity = InvocationIdentity(
        tenant_id="tenant-lease-a",
        agent_id="agent-lease-a",
        user_id="user-lease-a",
        session_id="session-lease-a",
        token_type="DEVELOPMENT",
    )
    job, _ = service.request_extraction(
        identity,
        ExtractionRequest(
            conversationId="conversation-lease-a",
            turnId="turn-lease-a",
            userMessage="记住租约测试。",
            assistantMessage="已了解。",
            occurredAt=datetime.now(UTC),
        ),
        "lease-extraction-key-0001",
    )

    first = repository.claim_extraction(job.extraction_id, lease_seconds=60)
    second = repository.claim_extraction(job.extraction_id, lease_seconds=60)

    assert first is not None
    assert first.status == "RUNNING"
    assert first.attempt_count == 1
    assert first.lease_until is not None
    assert second is None


class TemporarilyUnavailableExtractionModel:
    def extract(self, **_kwargs):
        raise RetryableExtractionError


def test_retryable_extraction_failure_releases_lease_and_reschedules_job() -> None:
    repository = InMemoryConversationMemoryRepository()
    service = LongTermMemoryService(
        repository,
        extraction_model=TemporarilyUnavailableExtractionModel(),
        max_attempts=3,
    )
    identity = InvocationIdentity(
        tenant_id="tenant-retry-a",
        agent_id="agent-retry-a",
        user_id="user-retry-a",
        session_id="session-retry-a",
        token_type="DEVELOPMENT",
    )
    job, _ = service.request_extraction(
        identity,
        ExtractionRequest(
            conversationId="conversation-retry-a",
            turnId="turn-retry-a",
            userMessage="重试测试",
            assistantMessage="已了解。",
            occurredAt=datetime.now(UTC),
        ),
        "retryable-extraction-key-0001",
    )

    service.process_extraction(job.extraction_id)
    rescheduled = repository.get_extraction(
        service.scope(identity), job.extraction_id
    )

    assert rescheduled is not None
    assert rescheduled.status == "PENDING"
    assert rescheduled.attempt_count == 1
    assert rescheduled.lease_until is None
    assert rescheduled.error_code == "RUNTIME_UNAVAILABLE"
    assert rescheduled.next_attempt_at > rescheduled.updated_at
