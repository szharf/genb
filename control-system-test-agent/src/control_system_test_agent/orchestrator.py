import asyncio
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from .clients import ControlSystemClient, GenBClient, PlanningReasoningClient, StandaloneShortTermMemoryClient
from .errors import RemoteCallError
from .models import ChatResult, ContextMessage, ExtractionStatus, LongTermMemoryItem


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


class StandaloneMemoryTestAgent:
    __test__ = False

    def __init__(
        self,
        *,
        agent_id: str,
        service_credential: str,
        genb: GenBClient,
        memory: StandaloneShortTermMemoryClient,
        answerer: Answerer,
    ) -> None:
        self._agent_id = agent_id
        self._service_credential = service_credential
        self._genb = genb
        self._memory = memory
        self._answerer = answerer

    async def chat(
        self, *, user_token: str, task_id: str, session_id: str, message: str
    ) -> ChatResult:
        component_session = await self._genb.issue_component_session(
            user_token=user_token,
            service_credential=self._service_credential,
            agent_id=self._agent_id,
            session_id=session_id,
            requested_components=("SHORT_TERM_MEMORY",),
        )
        endpoint = next(
            (
                item
                for item in component_session.components
                if item.component_code == "SHORT_TERM_MEMORY"
            ),
            None,
        )
        if endpoint is None:
            raise RemoteCallError(
                operation="resolve short-term memory binding",
                status_code=502,
                request_id=None,
            )

        request_id = f"req_{uuid4().hex}"
        prepared = await self._memory.prepare_context(
            base_url=endpoint.base_url,
            service_credential=self._service_credential,
            actor_token=component_session.actor_token,
            task_id=task_id,
            session_id=session_id,
            query=message,
            request_id=request_id,
        )
        answer = await self._answerer.answer(query=message, context=prepared.messages)
        unique = uuid4().hex
        await self._memory.commit_turn(
            base_url=endpoint.base_url,
            service_credential=self._service_credential,
            actor_token=component_session.actor_token,
            task_id=task_id,
            session_id=session_id,
            turn_id=f"turn_{unique}",
            user_message=message,
            assistant_message=answer,
            occurred_at=datetime.now(UTC).isoformat(),
            request_id=f"req_{uuid4().hex}",
            idempotency_key=f"idem_{unique}",
        )
        return ChatResult(
            answer=answer,
            context_message_count=len(prepared.messages),
            committed=True,
            warnings=(),
        )


    async def store_long_term(
        self, *, user_token: str, session_id: str, message: str
    ) -> ExtractionStatus:
        component_session = await self._genb.issue_component_session(
            user_token=user_token,
            service_credential=self._service_credential,
            agent_id=self._agent_id,
            session_id=session_id,
            requested_components=("LONG_TERM_MEMORY",),
        )
        unique = uuid4().hex
        extraction_id = await self._control.request_long_term_extraction(
            service_credential=self._service_credential,
            actor_token=component_session.actor_token,
            turn_id=f"turn_{unique}",
            user_message=message,
            assistant_message="已记录该长期信息。",
            occurred_at=datetime.now(UTC).isoformat(),
            request_id=f"req_{uuid4().hex}",
            idempotency_key=f"idem_{unique}",
        )
        for _ in range(30):
            result = await self._control.get_long_term_extraction(
                service_credential=self._service_credential,
                actor_token=component_session.actor_token,
                extraction_id=extraction_id,
                request_id=f"req_{uuid4().hex}",
            )
            if result.status in {"SUCCEEDED", "NO_WRITE", "FAILED", "DEAD"}:
                return result
            await asyncio.sleep(0.1)
        raise RemoteCallError(
            operation="wait long-term extraction", status_code=504, request_id=None
        )

    async def recall_long_term(
        self, *, user_token: str, session_id: str, query: str
    ) -> tuple[LongTermMemoryItem, ...]:
        component_session = await self._genb.issue_component_session(
            user_token=user_token,
            service_credential=self._service_credential,
            agent_id=self._agent_id,
            session_id=session_id,
            requested_components=("LONG_TERM_MEMORY",),
        )
        return await self._control.search_long_term_memory(
            service_credential=self._service_credential,
            actor_token=component_session.actor_token,
            query=query,
            request_id=f"req_{uuid4().hex}",
        )


class PlanningTestAgent:
    __test__ = False

    def __init__(
        self,
        *,
        agent_id: str,
        service_credential: str,
        genb: GenBClient,
        planning: PlanningReasoningClient,
    ) -> None:
        self._agent_id = agent_id
        self._service_credential = service_credential
        self._genb = genb
        self._planning = planning

    async def invoke(
        self,
        *,
        user_token: str,
        session_id: str,
        operation: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        component_session = await self._genb.issue_component_session(
            user_token=user_token,
            service_credential=self._service_credential,
            agent_id=self._agent_id,
            session_id=session_id,
            requested_components=("PLANNING_REASONING",),
        )
        endpoint = next(
            (
                item for item in component_session.components
                if item.component_code == "PLANNING_REASONING"
            ),
            None,
        )
        if endpoint is None:
            raise RemoteCallError(
                operation="resolve planning reasoning binding",
                status_code=502,
                request_id=None,
            )
        return await self._planning.invoke(
            base_url=endpoint.base_url,
            service_credential=self._service_credential,
            actor_token=component_session.actor_token,
            operation=operation,
            payload=payload,
            request_id=f"req_{uuid4().hex}",
        )
