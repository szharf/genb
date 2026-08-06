from unittest.mock import AsyncMock

import pytest

from control_system_test_agent.conversations import RedisConversationStore


@pytest.mark.asyncio
async def test_conversation_store_scopes_history_by_agent_user_and_scenario() -> None:
    redis = AsyncMock()
    redis.hvals.return_value = []
    store = RedisConversationStore(
        redis, "core-component-demo-agent", ttl_seconds=90 * 24 * 60 * 60
    )
    conversation = {
        "conversationId": "long-conversation-a",
        "scenario": "long",
        "title": "我的稳健偏好",
        "updatedAt": "2026-08-04T08:00:00+00:00",
    }

    await store.save(42, conversation)
    await store.list(42, "long")
    await store.list(7, "long")

    saved_key = redis.hset.await_args.args[0]
    listed_keys = [call.args[0] for call in redis.hvals.await_args_list]
    assert saved_key == "agent:core-component-demo-agent:user:42:conversations:long"
    assert listed_keys == [
        "agent:core-component-demo-agent:user:42:conversations:long",
        "agent:core-component-demo-agent:user:7:conversations:long",
    ]
    assert redis.expire.await_args.args == (saved_key, 90 * 24 * 60 * 60)
