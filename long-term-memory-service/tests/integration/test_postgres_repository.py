import os
from datetime import UTC, datetime
from uuid import uuid4

import psycopg2
import pytest
from psycopg2.extensions import parse_dsn

from long_term_memory.extraction import ExtractionCandidate, ExtractionModelResult
from long_term_memory.identity import InvocationIdentity
from long_term_memory.models import ExtractionRequest, SearchRequest
from long_term_memory.postgres_repository import PostgreSQLConversationMemoryRepository
from long_term_memory.service import LongTermMemoryService


class AcceptanceExtractionModel:
    def extract(self, *, user_message: str, assistant_message: str) -> ExtractionModelResult:
        del user_message, assistant_message
        return ExtractionModelResult(
            model="postgres-acceptance-model",
            candidates=(
                ExtractionCandidate(
                    memory_type="USER_PREFERENCE",
                    content="用户偏好本地PostgreSQL持久化。",
                    confidence=0.96,
                ),
            ),
        )


def _local_dsn() -> str:
    dsn = os.getenv("LONG_TERM_MEMORY_POSTGRES_DSN")
    if not dsn:
        pytest.skip("LONG_TERM_MEMORY_POSTGRES_DSN is not configured")
    host = parse_dsn(dsn).get("host", "localhost")
    assert host in {"localhost", "127.0.0.1", "::1"}, "integration test only accepts local PostgreSQL"
    return dsn


def test_postgres_persists_isolates_soft_deletes_and_leases() -> None:
    dsn = _local_dsn()
    suffix = uuid4().hex[:12]
    identity = InvocationIdentity(
        tenant_id=f"ltm-pg-tenant-{suffix}",
        user_id=f"ltm-pg-user-{suffix}",
        agent_id=f"ltm-pg-agent-{suffix}",
        session_id="session-a",
        token_type="DEVELOPMENT",
    )
    repository = PostgreSQLConversationMemoryRepository(dsn)
    repository.ensure_schema()
    service = LongTermMemoryService(
        repository,
        extraction_model=AcceptanceExtractionModel(),
    )
    request = ExtractionRequest(
        conversationId="conversation-pg-a",
        turnId=f"turn-{suffix}",
        userMessage="请记住我的本地数据库偏好。",
        assistantMessage="已了解。",
        occurredAt=datetime.now(UTC),
    )

    try:
        job, duplicate = service.request_extraction(
            identity, request, f"postgres-extraction-{suffix}"
        )
        same, duplicate_again = service.request_extraction(
            identity, request, f"postgres-extraction-{suffix}"
        )
        service.process_extraction(job.extraction_id)
        own = service.search(
            identity,
            SearchRequest(
                query="PostgreSQL",
                sourceTypes=["CONVERSATION"],
                topK=5,
            ),
        )
        other = service.search(
            InvocationIdentity(
                tenant_id=identity.tenant_id,
                user_id=identity.user_id,
                agent_id=f"other-{identity.agent_id}",
                session_id="session-b",
                token_type="DEVELOPMENT",
            ),
            SearchRequest(query="PostgreSQL", sourceTypes=["CONVERSATION"]),
        )
        corrected = service.correct_memory(
            identity,
            own.items[0].memory_id,
            content="用户偏好本地PostgreSQL持久化与审计。",
            reason="本地PostgreSQL更正验收",
        )
        confirmed = service.record_feedback(
            identity,
            corrected.memory_id,
            action="CONFIRM",
            reason="本地PostgreSQL反馈验收",
        )
        deleted = service.delete_memory(
            identity,
            corrected.memory_id,
            reason="本地PostgreSQL软删除验收",
        )
        after_delete = service.search(
            identity,
            SearchRequest(query="PostgreSQL", sourceTypes=["CONVERSATION"]),
        )
        lease_job, _ = service.request_extraction(
            identity,
            ExtractionRequest(
                conversationId="conversation-pg-lease",
                turnId=f"lease-{suffix}",
                userMessage="租约测试",
                assistantMessage="已了解。",
                occurredAt=datetime.now(UTC),
            ),
            f"postgres-lease-{suffix}",
        )
        first_claim = repository.claim_extraction(
            lease_job.extraction_id, lease_seconds=60
        )
        second_claim = repository.claim_extraction(
            lease_job.extraction_id, lease_seconds=60
        )
    finally:
        repository.close()

    reopened = PostgreSQLConversationMemoryRepository(dsn)
    try:
        persisted_job = reopened.get_extraction(identity_scope(identity), job.extraction_id)
        persisted_after_delete = LongTermMemoryService(reopened).search(
            identity,
            SearchRequest(query="PostgreSQL", sourceTypes=["CONVERSATION"]),
        )
    finally:
        reopened.close()
        _cleanup_scope(dsn, identity)

    assert not duplicate and duplicate_again
    assert same.extraction_id == job.extraction_id
    assert len(own.items) == 1 and other.items == ()
    assert corrected is not None and corrected.memory_id != own.items[0].memory_id
    assert confirmed is not None and confirmed.confidence > corrected.confidence
    assert deleted and after_delete.items == ()
    assert first_claim is not None and second_claim is None
    assert persisted_job is not None and persisted_job.status == "SUCCEEDED"
    assert persisted_after_delete.items == ()


def identity_scope(identity: InvocationIdentity) -> tuple[str, str, str]:
    return identity.tenant_id, identity.user_id, identity.agent_id


def _cleanup_scope(dsn: str, identity: InvocationIdentity) -> None:
    scope = identity_scope(identity)
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            for table in ("memory_audit_events", "long_term_memories", "memory_extraction_jobs"):
                cursor.execute(
                    f'DELETE FROM long_term_memory_service."{table}" '
                    "WHERE tenant_id=%s AND user_id=%s AND agent_id=%s",
                    scope,
                )
