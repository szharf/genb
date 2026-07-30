import asyncio
import json
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from .clients import ControlSystemClient, GenBClient, PlanningReasoningClient, RuntimeInferenceClient, StandaloneShortTermMemoryClient
from .errors import RemoteCallError
from .models import ChatResult, ContextMessage, CustomerChatResult, CustomerDiagnostics, ExtractionStatus, LongTermMemoryItem


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


class CustomerCoreComponentAgent:
    __test__ = False

    def __init__(
        self,
        *,
        agent_id: str,
        service_credential: str,
        genb: GenBClient,
        memory: StandaloneShortTermMemoryClient,
        inference: RuntimeInferenceClient,
        planning: PlanningReasoningClient,
    ) -> None:
        self._agent_id = agent_id
        self._service_credential = service_credential
        self._genb = genb
        self._memory = memory
        self._inference = inference
        self._planning = planning

    async def chat(
        self, *, user_token: str, task_id: str, session_id: str, message: str
    ) -> CustomerChatResult:
        component_session = await self._genb.issue_component_session(
            user_token=user_token,
            service_credential=self._service_credential,
            agent_id=self._agent_id,
            session_id=session_id,
            requested_components=("SHORT_TERM_MEMORY", "PLANNING_REASONING", "INFERENCE_ENGINE"),
        )
        endpoints = {item.component_code: item for item in component_session.components}
        missing = {
            "SHORT_TERM_MEMORY", "PLANNING_REASONING", "INFERENCE_ENGINE"
        } - endpoints.keys()
        if missing:
            raise RemoteCallError(
                operation="resolve customer agent bindings", status_code=403, request_id=None
            )

        memory_request_id = f"req_{uuid4().hex}"
        prepared = await self._memory.prepare_context(
            base_url=endpoints["SHORT_TERM_MEMORY"].base_url,
            service_credential=self._service_credential,
            actor_token=component_session.actor_token,
            task_id=task_id,
            session_id=session_id,
            query=message,
            request_id=memory_request_id,
        )
        model_request_id = f"req_{uuid4().hex}"
        model_result = await self._inference.complete(
            base_url=endpoints["INFERENCE_ENGINE"].base_url,
            service_credential=self._service_credential,
            actor_token=component_session.actor_token,
            messages=_customer_messages(prepared.messages, message),
            request_id=model_request_id,
        )
        decision = _customer_decision(model_result.content)
        answer = str(decision.get("answer") or "暂时无法生成有效回答，请补充需求。")
        mode = str(decision.get("intent") or "CHAT")
        skill_result: dict[str, object] | None = None
        planning_operation: str | None = None
        if mode == "CREATE_SKILL":
            skill_request = _skill_request(decision.get("skill"), source_message=message)
            requirements = skill_request["requirements"]
            analysis = await self._planning.invoke(
                base_url=endpoints["PLANNING_REASONING"].base_url,
                service_credential=self._service_credential,
                actor_token=component_session.actor_token,
                operation="ANALYZE",
                payload=requirements,
                request_id=f"req_{uuid4().hex}",
            )
            planning_operation = "ANALYZE"
            if analysis.get("status") == "NEEDS_CLARIFICATION":
                questions = analysis.get("questions")
                question_texts = [
                    str(item.get("question"))
                    for item in questions
                    if isinstance(item, dict) and item.get("question")
                ] if isinstance(questions, list) else []
                answer = "为了准确生成Skill，请继续确认：\n" + "\n".join(
                    f"{index}. {question}" for index, question in enumerate(question_texts, start=1)
                )
                mode = "PLANNING_CLARIFICATION"
            else:
                skill_result = await self._planning.invoke(
                    base_url=endpoints["PLANNING_REASONING"].base_url,
                    service_credential=self._service_credential,
                    actor_token=component_session.actor_token,
                    operation="GENERATE",
                    payload=skill_request,
                    request_id=f"req_{uuid4().hex}",
                )
                planning_operation = "GENERATE"
                validation = skill_result.get("validation")
                if not isinstance(validation, dict) or validation.get("valid") is not True:
                    answer = "Skill草稿已生成，但未通过结构校验，系统没有将它标记为可用。请联系管理员查看校验问题。"
                    mode = "SKILL_VALIDATION_FAILED"
                else:
                    answer = f"已经生成Skill：{skill_result.get('name', skill_request['name'])}，请查看下方完整内容。"
                    mode = "SKILL_GENERATED"
        unique = uuid4().hex
        await self._memory.commit_turn(
            base_url=endpoints["SHORT_TERM_MEMORY"].base_url,
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
        return CustomerChatResult(
            answer=answer,
            mode=mode,
            skill=skill_result,
            committed=True,
            diagnostics=CustomerDiagnostics(
                component_session_id=component_session.component_session_id,
                components=tuple(endpoints),
                context_message_count=len(prepared.messages),
                provider=model_result.provider,
                model=model_result.model,
                input_tokens=model_result.input_tokens,
                output_tokens=model_result.output_tokens,
                request_id=model_result.request_id,
                planning_operation=planning_operation,
            ),
        )


def _customer_messages(
    context: tuple[ContextMessage, ...], message: str
) -> list[dict[str, str]]:
    system = (
        "你是面向银行客户的核心组件验证智能体。请结合历史上下文回答当前问题。"
        "只返回一个合法JSON对象，不要输出代码围栏、解释或原始思维链。"
        "普通问答格式为：{\"intent\":\"CHAT\",\"answer\":\"给客户的自然中文回答\",\"skill\":null}。"
        "只有用户明确要求创建、生成或编写Skill时，才使用CREATE_SKILL，格式必须为："
        "{\"intent\":\"CREATE_SKILL\",\"answer\":\"已开始梳理需求\",\"skill\":{"
        "\"name\":\"简短Skill名称\",\"description\":\"不少于十个字的用途说明\","
        "\"goal\":\"明确目标\",\"expectedInputs\":[\"输入\"],\"expectedOutputs\":[\"输出\"],"
        "\"constraints\":[\"约束\"],\"preferredTools\":[],\"toolReferences\":[],\"riskLevel\":\"LOW\"}}。"
        "用户没有说明的数组字段必须返回空数组，不得省略字段或自行编造关键业务信息。"
    )
    messages = [{"role": "system", "content": system}]
    messages.extend({"role": item.role, "content": item.content} for item in context)
    messages.append({"role": "user", "content": message})
    return messages


def _customer_decision(content: str) -> dict[str, object]:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        first_newline = stripped.find("\n")
        stripped = stripped[first_newline + 1 : -3].strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as error:
        raise RemoteCallError(
            operation="parse customer model response", status_code=502, request_id=None
        ) from error
    if not isinstance(value, dict) or value.get("intent") not in {"CHAT", "CREATE_SKILL"}:
        raise RemoteCallError(
            operation="validate customer model response", status_code=502, request_id=None
        )
    return value


def _skill_request(value: object, *, source_message: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RemoteCallError(
            operation="validate customer skill request", status_code=502, request_id=None
        )
    required_text = ("name", "description", "goal")
    if any(not isinstance(value.get(key), str) or not str(value[key]).strip() for key in required_text):
        raise RemoteCallError(
            operation="validate customer skill request", status_code=502, request_id=None
        )
    expected_inputs = _string_list(value.get("expectedInputs"))
    expected_outputs = _string_list(value.get("expectedOutputs"))
    constraints = _string_list(value.get("constraints"))
    # The model may suggest structure, but it must not silently invent the three
    # acceptance-critical requirement groups.  Missing facts remain missing so
    # the planning component can ask the customer before authoring a Skill.
    if not any(marker in source_message for marker in ("输入为", "输入是", "输入包括", "所需材料", "提供材料")):
        expected_inputs = []
    if not any(marker in source_message for marker in ("输出为", "输出是", "输出包括", "产出为", "产出是")):
        expected_outputs = []
    if not any(marker in source_message for marker in ("约束", "不得", "必须", "仅限", "人工复核")):
        constraints = []
    requirements = {
        "goal": value["goal"],
        "expectedInputs": expected_inputs,
        "expectedOutputs": expected_outputs,
        "constraints": constraints,
        "preferredTools": _string_list(value.get("preferredTools")),
        "toolReferences": value.get("toolReferences") if isinstance(value.get("toolReferences"), list) else [],
        "riskLevel": value.get("riskLevel") if value.get("riskLevel") in {"LOW", "MEDIUM", "HIGH"} else "LOW",
    }
    return {
        "name": value["name"],
        "description": value["description"],
        "requirements": requirements,
    }


def _string_list(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []
