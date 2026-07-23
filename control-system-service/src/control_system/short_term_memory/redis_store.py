import hashlib
import hmac
import json
from datetime import datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError

from .models import ConversationTurn, StoreCommitResult, StoredMessage
from .store import IdempotencyConflictError, ScopeKey, StoreUnavailableError

_COMMIT_SCRIPT = """
local previous = redis.call('GET', KEYS[4])
if previous then
  local decoded = cjson.decode(previous)
  if decoded.fingerprint ~= ARGV[1] then
    return {-1, ''}
  end
  return {1, cjson.encode(decoded.result)}
end

redis.call('RPUSH', KEYS[1], ARGV[2], ARGV[3])
redis.call('LTRIM', KEYS[1], -tonumber(ARGV[5]), -1)
local message_count = redis.call('LLEN', KEYS[1])
redis.call('HSET', KEYS[2], 'lastTurnId', ARGV[4])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[6]))
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[6]))
if redis.call('EXISTS', KEYS[3]) == 1 then
  redis.call('EXPIRE', KEYS[3], tonumber(ARGV[6]))
end

local result = {turnId = ARGV[4], messageCount = message_count}
redis.call(
  'SET',
  KEYS[4],
  cjson.encode({fingerprint = ARGV[1], result = result}),
  'EX',
  tonumber(ARGV[6])
)
return {0, cjson.encode(result)}
"""


class RedisSessionStore:
    def __init__(
        self,
        client: Redis,
        *,
        key_prefix: str = "genb:cs:v1",
        key_pepper: bytes,
    ) -> None:
        if len(key_pepper) < 16:
            raise ValueError("Redis key pepper must contain at least 16 bytes")
        self._client = client
        self._key_prefix = key_prefix.rstrip(":")
        self._key_pepper = key_pepper

    async def health(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False

    async def commit(
        self,
        scope: ScopeKey,
        turn: ConversationTurn,
        idempotency_key: str,
        request_fingerprint: str,
        *,
        max_messages: int,
        ttl_seconds: int,
    ) -> StoreCommitResult:
        messages_key, meta_key, summary_key = self._session_keys(scope)
        idempotency_key_name = self._idempotency_key(scope, idempotency_key)
        user_message = _message_json(turn, "user", turn.user_message)
        assistant_message = _message_json(
            turn, "assistant", turn.assistant_message
        )
        try:
            response = await self._client.eval(
                _COMMIT_SCRIPT,
                4,
                messages_key,
                meta_key,
                summary_key,
                idempotency_key_name,
                request_fingerprint,
                user_message,
                assistant_message,
                turn.turn_id,
                max_messages,
                ttl_seconds,
            )
            result_code = int(response[0])
            if result_code == -1:
                raise IdempotencyConflictError
            result = json.loads(response[1])
            return StoreCommitResult(
                turn_id=result["turnId"],
                duplicate=result_code == 1,
                message_count=int(result["messageCount"]),
            )
        except IdempotencyConflictError:
            raise
        except (RedisError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise StoreUnavailableError from error

    async def read(self, scope: ScopeKey) -> list[StoredMessage]:
        messages_key, _, _ = self._session_keys(scope)
        try:
            encoded_messages = await self._client.lrange(messages_key, 0, -1)
            messages: list[StoredMessage] = []
            for encoded_message in encoded_messages:
                payload = json.loads(encoded_message)
                messages.append(
                    StoredMessage(
                        turn_id=payload["turnId"],
                        role=payload["role"],
                        content=payload["content"],
                        occurred_at=datetime.fromisoformat(payload["occurredAt"]),
                    )
                )
            return messages
        except (RedisError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise StoreUnavailableError from error

    async def clear(self, scope: ScopeKey) -> bool:
        keys = self._session_keys(scope)
        try:
            return bool(await self._client.delete(*keys))
        except RedisError as error:
            raise StoreUnavailableError from error

    def _session_keys(self, scope: ScopeKey) -> tuple[str, str, str]:
        scope_hashes = ":".join(self._hash(value) for value in scope)
        base = f"{self._key_prefix}:stm:{scope_hashes}"
        return f"{base}:messages", f"{base}:meta", f"{base}:summary"

    def _idempotency_key(self, scope: ScopeKey, idempotency_key: str) -> str:
        scope_hash = self._hash("\x1f".join(scope))
        return f"{self._key_prefix}:idem:{scope_hash}:{self._hash(idempotency_key)}"

    def _hash(self, value: str) -> str:
        return hmac.new(
            self._key_pepper,
            value.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:32]


def _message_json(
    turn: ConversationTurn,
    role: str,
    content: str,
) -> str:
    return json.dumps(
        {
            "turnId": turn.turn_id,
            "role": role,
            "content": content,
            "occurredAt": turn.occurred_at.isoformat(),
            "contentVersion": 1,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
