from __future__ import annotations

import json


class RedisConversationStore:
    """Persist user-owned conversation snapshots behind a small Redis interface."""

    def __init__(self, redis, agent_id: str, *, ttl_seconds: int) -> None:
        self._redis = redis
        self._agent_id = agent_id
        self._ttl_seconds = ttl_seconds

    async def save(self, user_id: int, conversation: dict[str, object]) -> None:
        key = self._key(user_id, str(conversation["scenario"]))
        await self._redis.hset(
            key,
            str(conversation["conversationId"]),
            json.dumps(conversation, ensure_ascii=False, separators=(",", ":")),
        )
        await self._redis.expire(key, self._ttl_seconds)

    async def list(self, user_id: int, scenario: str) -> list[dict[str, object]]:
        values = await self._redis.hvals(self._key(user_id, scenario))
        conversations = [json.loads(value) for value in values]
        conversations.sort(key=lambda item: str(item.get("updatedAt", "")), reverse=True)
        return conversations[:50]

    def _key(self, user_id: int, scenario: str) -> str:
        return f"agent:{self._agent_id}:user:{user_id}:conversations:{scenario}"
