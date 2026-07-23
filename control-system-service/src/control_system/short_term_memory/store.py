from typing import Protocol

from .models import ConversationSummary, ConversationTurn, StoreCommitResult, StoredMessage

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

    async def read_summary(self, scope: ScopeKey) -> ConversationSummary | None: ...

    async def write_summary(
        self,
        scope: ScopeKey,
        summary: ConversationSummary,
        *,
        expected_through_turn_id: str | None,
        ttl_seconds: int,
    ) -> bool: ...

    async def clear(self, scope: ScopeKey) -> bool: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._messages: dict[ScopeKey, list[StoredMessage]] = {}
        self._idempotency: dict[
            tuple[ScopeKey, str], tuple[str, StoreCommitResult]
        ] = {}
        self._summaries: dict[ScopeKey, ConversationSummary] = {}

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

    async def read_summary(self, scope: ScopeKey) -> ConversationSummary | None:
        return self._summaries.get(scope)

    async def write_summary(
        self,
        scope: ScopeKey,
        summary: ConversationSummary,
        *,
        expected_through_turn_id: str | None,
        ttl_seconds: int,
    ) -> bool:
        del ttl_seconds
        current = self._summaries.get(scope)
        current_through = current.through_turn_id if current else None
        if current_through != expected_through_turn_id:
            return False
        self._summaries[scope] = summary
        return True

    async def clear(self, scope: ScopeKey) -> bool:
        messages_existed = self._messages.pop(scope, None) is not None
        summary_existed = self._summaries.pop(scope, None) is not None
        return messages_existed or summary_existed


class IdempotencyConflictError(Exception):
    pass


class StoreUnavailableError(Exception):
    pass
