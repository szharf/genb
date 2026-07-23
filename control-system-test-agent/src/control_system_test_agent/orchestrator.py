from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from .clients import ControlSystemClient, GenBClient
from .errors import RemoteCallError
from .models import ChatResult, ContextMessage


class Answerer(Protocol):
    async def answer(
        self, *, query: str, context: tuple[ContextMessage, ...]
    ) -> str: ...


class DeterministicAnswerer:
    """Test-only answerer that keeps model availability out of memory acceptance."""

    async def answer(
        self, *, query: str, context: tuple[ContextMessage, ...]
    ) -> str:
        return f"测试回答（已读取{len(context)}条上下文）：{query}"


class TestAgent:
    __test__ = False

    def __init__(
        self,
        *,
        agent_id: str,
        service_credential: str,
        genb: GenBClient,
        control: ControlSystemClient,
        answerer: Answerer,
        max_context_tokens: int = 2000,
    ) -> None:
        self._agent_id = agent_id
        self._service_credential = service_credential
        self._genb = genb
        self._control = control
        self._answerer = answerer
        self._max_context_tokens = max_context_tokens

    async def chat(
        self, *, user_token: str, session_id: str, message: str
    ) -> ChatResult:
        component_session = await self._genb.issue_component_session(
            user_token=user_token,
            service_credential=self._service_credential,
            agent_id=self._agent_id,
            session_id=session_id,
            requested_components=("SHORT_TERM_MEMORY",),
        )
        warnings: list[str] = []
        context: tuple[ContextMessage, ...] = ()
        try:
            prepared = await self._control.prepare_context(
                service_credential=self._service_credential,
                actor_token=component_session.actor_token,
                query=message,
                max_context_tokens=self._max_context_tokens,
                request_id=f"req_{uuid4().hex}",
            )
            context = prepared.messages
        except RemoteCallError:
            warnings.append("SHORT_TERM_PREPARE_UNAVAILABLE")

        answer = await self._answerer.answer(query=message, context=context)
        committed = True
        try:
            unique = uuid4().hex
            await self._control.commit_turn(
                service_credential=self._service_credential,
                actor_token=component_session.actor_token,
                turn_id=f"turn_{unique}",
                user_message=message,
                assistant_message=answer,
                occurred_at=datetime.now(UTC).isoformat(),
                request_id=f"req_{uuid4().hex}",
                idempotency_key=f"idem_{unique}",
            )
        except RemoteCallError:
            committed = False
            warnings.append("SHORT_TERM_COMMIT_UNAVAILABLE")
        return ChatResult(
            answer=answer,
            context_message_count=len(context),
            committed=committed,
            warnings=tuple(warnings),
        )
