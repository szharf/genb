import hashlib
import json
from dataclasses import replace

from .models import ConversationTurn, StoreCommitResult, StoredMessage
from .redaction import redact_sensitive_content
from .store import (
    IdempotencyConflictError,
    ScopeKey,
    SessionStore,
    StoreUnavailableError,
)
from ..errors import DependencyProblem, IdempotencyProblem
from ..identity import InvocationIdentity


class ShortTermMemoryService:
    def __init__(
        self,
        store: SessionStore,
        *,
        ttl_seconds: int = 86400,
        max_turns: int = 50,
    ) -> None:
        self._store = store
        self._ttl_seconds = ttl_seconds
        self._max_messages = max_turns * 2

    @staticmethod
    def _scope(identity: InvocationIdentity) -> ScopeKey:
        if identity.session_id is None:
            raise ValueError("Actor Token must contain a sessionId")
        return (
            identity.tenant_id,
            identity.user_id,
            identity.agent_id,
            identity.session_id,
        )

    async def commit_turn(
        self,
        identity: InvocationIdentity,
        turn: ConversationTurn,
        idempotency_key: str,
    ) -> StoreCommitResult:
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "turnId": turn.turn_id,
                    "userMessage": turn.user_message,
                    "assistantMessage": turn.assistant_message,
                    "occurredAt": turn.occurred_at.isoformat(),
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        safe_turn = replace(
            turn,
            user_message=redact_sensitive_content(turn.user_message),
            assistant_message=redact_sensitive_content(turn.assistant_message),
        )
        try:
            return await self._store.commit(
                self._scope(identity),
                safe_turn,
                idempotency_key,
                fingerprint,
                max_messages=self._max_messages,
                ttl_seconds=self._ttl_seconds,
            )
        except IdempotencyConflictError as error:
            raise IdempotencyProblem(identity.request_id) from error
        except StoreUnavailableError as error:
            raise DependencyProblem(identity.request_id) from error

    async def prepare_context(
        self,
        identity: InvocationIdentity,
        *,
        max_context_tokens: int,
    ) -> tuple[list[StoredMessage], int, int]:
        try:
            messages = await self._store.read(self._scope(identity))
        except StoreUnavailableError as error:
            raise DependencyProblem(identity.request_id) from error
        message_groups: list[list[StoredMessage]] = []
        for message in messages:
            if not message_groups or message_groups[-1][0].turn_id != message.turn_id:
                message_groups.append([message])
            else:
                message_groups[-1].append(message)
        selected_groups: list[list[StoredMessage]] = []
        used_tokens = 0
        for group in reversed(message_groups):
            group_tokens = sum(_estimate_tokens(message.content) for message in group)
            if used_tokens + group_tokens > max_context_tokens:
                break
            selected_groups.append(group)
            used_tokens += group_tokens
        selected = [
            message
            for group in reversed(selected_groups)
            for message in group
        ]
        return selected, len(messages) - len(selected), used_tokens

    async def clear_session(self, identity: InvocationIdentity) -> bool:
        try:
            return await self._store.clear(self._scope(identity))
        except StoreUnavailableError as error:
            raise DependencyProblem(identity.request_id) from error


def _estimate_tokens(content: str) -> int:
    return max(1, (len(content.encode("utf-8")) + 2) // 3)
