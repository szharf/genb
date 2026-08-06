import os
from datetime import UTC, datetime
from uuid import uuid4

import psycopg2
import pytest

from control_system.long_term_memory.config import LongTermMemoryRuntimeConfig
from control_system.long_term_memory.extraction import ExtractionCandidate, ExtractionModelResult
from control_system.long_term_memory.postgres_repository import PostgreSQLLongTermMemoryRepository
from control_system.long_term_memory.worker import ExtractionWorker


class AcceptanceModel:
    async def extract(self, request):
        return ExtractionModelResult(
            model="iteration13-contract-model",
            candidates=(ExtractionCandidate(
                memory_type="USER_PREFERENCE",
                content=f"iteration13 contract preference {request.request_id}",
                confidence=0.96,
                action="UPSERT",
            ),),
        )


@pytest.mark.asyncio
async def test_postgres_contract_is_scoped_idempotent_and_soft_deletable() -> None:
    dsn = os.getenv("CONTROL_SYSTEM_POSTGRES_DSN")
    if not dsn:
        pytest.skip("CONTROL_SYSTEM_POSTGRES_DSN is not configured")
    suffix = uuid4().hex[:12]
    scope = (f"iteration13-tenant-{suffix}", f"iteration13-user-{suffix}", f"iteration13-agent-{suffix}")
    other_agent = (scope[0], scope[1], f"iteration13-other-{suffix}")
    repository = PostgreSQLLongTermMemoryRepository(dsn)
    config = LongTermMemoryRuntimeConfig(
        enabled_types=frozenset({"USER_PREFERENCE"}),
        auto_extraction_enabled=True,
        confidence_threshold=0.8,
        retention_days=30,
        top_k=5,
        max_top_k=10,
        model_alias="iteration13-contract-model",
        max_attempts=2,
    )
    try:
        job, duplicate = await repository.create_extraction(
            scope,
            turn_id=f"turn-{suffix}",
            user_message="durable preference",
            assistant_message="noted",
            occurred_at=datetime.now(UTC),
            idempotency_hash=("a" + suffix).ljust(64, "0"),
            request_fingerprint=("b" + suffix).ljust(64, "0"),
            config_version_id=13,
            config=config,
        )
        same, duplicate_again = await repository.create_extraction(
            scope,
            turn_id=f"turn-{suffix}",
            user_message="durable preference",
            assistant_message="noted",
            occurred_at=datetime.now(UTC),
            idempotency_hash=("a" + suffix).ljust(64, "0"),
            request_fingerprint=("b" + suffix).ljust(64, "0"),
            config_version_id=13,
            config=config,
        )
        status = await ExtractionWorker(
            repository, extraction_model=AcceptanceModel()
        ).process(job.extraction_id, f"request-{suffix}", None)
        own = await repository.search(
            scope, query="iteration13", types=frozenset({"USER_PREFERENCE"}),
            source_types=frozenset({"CONVERSATION"}), limit=5
        )
        isolated = await repository.search(
            other_agent, query="iteration13", types=frozenset({"USER_PREFERENCE"}),
            source_types=frozenset({"CONVERSATION"}), limit=5
        )
        deleted = await repository.delete_memory(
            scope, own[0].memory_id, actor="acceptance", reason="contract soft delete",
            request_id=f"request-{suffix}",
        )
        after_delete = await repository.search(
            scope, query="iteration13", types=frozenset({"USER_PREFERENCE"}),
            source_types=frozenset({"CONVERSATION"}), limit=5
        )
    finally:
        await repository.close()

    assert not duplicate and duplicate_again and same.extraction_id == job.extraction_id
    assert status == "SUCCEEDED" and len(own) == 1
    assert own[0].source_type == "CONVERSATION"
    assert isolated == [] and deleted and after_delete == []


@pytest.mark.asyncio
async def test_postgres_search_applies_memory_source_filter_without_live_database() -> None:
    captured: dict[str, object] = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement, parameters) -> None:
            captured["statement"] = statement
            captured["parameters"] = parameters

        def fetchall(self) -> list[object]:
            return []

    class FakeConnection:
        def cursor(self, **_kwargs) -> FakeCursor:
            return FakeCursor()

    repository = object.__new__(PostgreSQLLongTermMemoryRepository)

    async def run(operation):
        return operation(FakeConnection())

    repository._run = run
    result = await repository.search(
        ("tenant-a", "user-a", "agent-a"),
        query="policy",
        types=frozenset({"STABLE_FACT"}),
        source_types=frozenset({"KNOWLEDGE_BASE"}),
        limit=5,
    )

    assert result == []
    assert "source_type = ANY" in str(captured["statement"])
    assert captured["parameters"][5] == ["KNOWLEDGE_BASE"]


def test_long_term_tables_have_no_physical_foreign_keys() -> None:
    dsn = os.getenv("CONTROL_SYSTEM_POSTGRES_DSN")
    if not dsn:
        pytest.skip("CONTROL_SYSTEM_POSTGRES_DSN is not configured")
    names = [
        "long_term_memories", "memory_extraction_jobs",
        "memory_extraction_events", "memory_audit_events",
    ]
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*) FROM information_schema.table_constraints
                WHERE table_schema=current_schema() AND table_name=ANY(%s)
                  AND constraint_type='FOREIGN KEY'
                """,
                (names,),
            )
            assert cursor.fetchone()[0] == 0
