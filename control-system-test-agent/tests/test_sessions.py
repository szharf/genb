from unittest.mock import AsyncMock

import pytest

from control_system_test_agent.sessions import CustomerSession, RedisCustomerSessionStore


@pytest.mark.asyncio
async def test_redis_session_store_hashes_cookie_ids_and_round_trips_minimum_context() -> None:
    redis = AsyncMock()
    redis.set.return_value = True
    session = CustomerSession(
        "server-only-session-grant", "core-component-demo-agent", 42, "customer-a"
    )
    store = RedisCustomerSessionStore(redis, "core-component-demo-agent", ttl_seconds=28800)

    session_id = await store.create(session)
    key = redis.set.await_args.args[0]
    stored = redis.set.await_args.args[1]

    assert session_id not in key
    assert key.startswith("agent:core-component-demo-agent:session:")
    assert "server-only-session-grant" in stored
    assert redis.set.await_args.kwargs["ex"] == 28800
