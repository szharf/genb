from typing import Protocol

from .models import ConversationTurn, StoreCommitResult, StoredMessage

ScopeKey = tuple[str, str, str, str]


class SessionStore(Protocol):
    async def health(self) -> bool: ...

    async def commit(
        self,
        scope: ScopeKey,
        turn: ConversationTurn,
        idempotency_key: str,
        request_fingerprint: str,
        *,
        max_messages: int,
        ttl_seconds: int,
    ) -> StoreCommitResult: ...

    async def read(self, scope: ScopeKey) -> list[StoredMessage]: ...

    async def clear(self, scope: ScopeKey) -> bool: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._messages: dict[ScopeKey, list[StoredMessage]] = {}
        self._idempotency: dict[
            tuple[ScopeKey, str], tuple[str, StoreCommitResult]
        ] = {}

    async def health(self) -> bool:
        return True

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
        del ttl_seconds
        idempotency_scope = (scope, idempotency_key)
        previous_entry = self._idempotency.get(idempotency_scope)
        if previous_entry is not None:
            previous_fingerprint, previous = previous_entry
            if previous_fingerprint != request_fingerprint:
                raise IdempotencyConflictError
            return StoreCommitResult(
                turn_id=previous.turn_id,
                duplicate=True,
                message_count=previous.message_count,
            )
        messages = self._messages.setdefault(scope, [])
        messages.extend(
            [
                StoredMessage(turn.turn_id, "user", turn.user_message, turn.occurred_at),
                StoredMessage(
                    turn.turn_id,
                    "assistant",
                    turn.assistant_message,
                    turn.occurred_at,
                ),
            ]
        )
        if len(messages) > max_messages:
            del messages[:-max_messages]
        result = StoreCommitResult(turn.turn_id, False, len(messages))
        self._idempotency[idempotency_scope] = (request_fingerprint, result)
        return result

    async def read(self, scope: ScopeKey) -> list[StoredMessage]:
        return list(self._messages.get(scope, []))

    async def clear(self, scope: ScopeKey) -> bool:
        return self._messages.pop(scope, None) is not None


class IdempotencyConflictError(Exception):
    pass


class StoreUnavailableError(Exception):
    pass
