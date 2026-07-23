import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from control_system.short_term_memory.models import ConversationSummary, ConversationTurn
from control_system.short_term_memory.redis_store import RedisSessionStore
from control_system.short_term_memory.store import IdempotencyConflictError


def test_redis_adapter_is_atomic_ttl_scoped_and_uses_hashed_keys() -> None:
    password = os.getenv("CONTROL_SYSTEM_TEST_REDIS_PASSWORD")
    if not password:
        pytest.skip("CONTROL_SYSTEM_TEST_REDIS_PASSWORD is required")
    asyncio.run(_exercise_redis_adapter(password))


async def _exercise_redis_adapter(password: str) -> None:
    run_id = uuid4().hex
    prefix = f"genb:cs:test:{run_id}"
    client = Redis(
        host="127.0.0.1",
        port=6379,
        password=password,
        db=15,
        decode_responses=True,
    )
    store = RedisSessionStore(
        client,
        key_prefix=prefix,
        key_pepper=b"iteration-9-test-pepper",
    )
    scope = ("tenant-private", "user-private", "agent-private", "session-private")
    turn = ConversationTurn(
        turn_id="turn-0001",
        user_message="hello",
        assistant_message="world",
        occurred_at=datetime(2026, 7, 23, 10, 0, tzinfo=UTC),
    )
    try:
        first = await store.commit(
            scope,
            turn,
            "idem-redis-commit-0001",
            "fingerprint-a",
            max_messages=4,
            ttl_seconds=120,
        )
        duplicate = await store.commit(
            scope,
            turn,
            "idem-redis-commit-0001",
            "fingerprint-a",
            max_messages=4,
            ttl_seconds=120,
        )
        with pytest.raises(IdempotencyConflictError):
            await store.commit(
                scope,
                turn,
                "idem-redis-commit-0001",
                "fingerprint-b",
                max_messages=4,
                ttl_seconds=120,
            )
        isolated_scope = (
            scope[0],
            "another-user",
            scope[2],
            "another-session",
        )
        isolated = await store.commit(
            isolated_scope,
            turn,
            "idem-redis-commit-0001",
            "fingerprint-b",
            max_messages=4,
            ttl_seconds=120,
        )
        messages = await store.read(scope)
        summary = ConversationSummary(
            summary="safe summary",
            through_turn_id="turn-0001",
            model="summary-model",
            updated_at=datetime(2026, 7, 23, 10, 1, tzinfo=UTC),
        )
        summary_written = await store.write_summary(
            scope,
            summary,
            expected_through_turn_id=None,
            ttl_seconds=120,
        )
        stale_rejected = not await store.write_summary(
            scope,
            ConversationSummary(
                summary="stale",
                through_turn_id="turn-0000",
                model="summary-model",
                updated_at=datetime(2026, 7, 23, 10, 2, tzinfo=UTC),
            ),
            expected_through_turn_id=None,
            ttl_seconds=120,
        )
        stored_summary = await store.read_summary(scope)
        keys = [key async for key in client.scan_iter(match=f"{prefix}:*")]
        ttl_values = [await client.ttl(key) for key in keys]
        cleared = await store.clear(scope)
        isolated_session_keys = [
            key
            async for key in client.scan_iter(match=f"{prefix}:stm:*")
        ]
    finally:
        keys_to_remove = [key async for key in client.scan_iter(match=f"{prefix}:*")]
        if keys_to_remove:
            await client.delete(*keys_to_remove)
        await client.aclose()

    assert first.duplicate is False
    assert duplicate.duplicate is True
    assert isolated.duplicate is False
    assert len(messages) == 2
    assert summary_written is True
    assert stale_rejected is True
    assert stored_summary == summary
    assert keys
    assert all(value > 0 for value in ttl_values)
    assert all(raw not in key for key in keys for raw in scope)
    assert cleared is True
    assert len(isolated_session_keys) == 2
