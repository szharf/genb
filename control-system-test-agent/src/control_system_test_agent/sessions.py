from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CustomerSession:
    session_grant: str
    agent_id: str
    user_id: int
    username: str


class RedisCustomerSessionStore:
    def __init__(self, redis, agent_id: str, *, ttl_seconds: int) -> None:
        self._redis = redis
        self._agent_id = agent_id
        self._ttl_seconds = ttl_seconds

    async def create(self, session: CustomerSession) -> str:
        session_id = secrets.token_urlsafe(32)
        await self._redis.set(
            self._key(session_id),
            json.dumps(asdict(session), ensure_ascii=False, separators=(",", ":")),
            ex=self._ttl_seconds,
        )
        return session_id

    async def get(self, session_id: str) -> CustomerSession | None:
        if not session_id:
            return None
        value = await self._redis.get(self._key(session_id))
        if value is None:
            return None
        data = json.loads(value)
        session = CustomerSession(**data)
        if session.agent_id != self._agent_id:
            return None
        return session

    async def delete(self, session_id: str) -> None:
        if session_id:
            await self._redis.delete(self._key(session_id))

    def _key(self, session_id: str) -> str:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        return f"agent:{self._agent_id}:session:{digest}"
