from dataclasses import dataclass

import pytest

from control_system_test_agent.models import (
    ActorSession,
    CommitResult,
    ComponentEndpoint,
    ContextMessage,
    InferenceResult,
    PreparedContext,
)
from control_system_test_agent.orchestrator import CustomerCoreComponentAgent, _customer_decision


def test_customer_decision_accepts_a_json_object_wrapped_by_model_commentary():
    result = _customer_decision(
        '我会按约定判断。\n{"intent":"CREATE_SKILL","answer":"继续梳理需求","skill":null}\n以上。'
    )

    assert result["intent"] == "CREATE_SKILL"


def _endpoint(code: str, port: int) -> ComponentEndpoint:
    return ComponentEndpoint(code, f"{code.lower()}-v1", f"http://127.0.0.1:{port}", "1.0.0", 1, ())


@dataclass
class FakeGenB:
    requested: tuple[str, ...] = ()
    session_grant: str = ""

    async def issue_component_session(self, **kwargs):
        self.requested = tuple(kwargs["requested_components"])
        self.session_grant = kwargs.get("session_grant", "")
        return ActorSession(
            "cs-customer",
            "actor-token",
            "2099-01-01T00:00:00Z",
            (
                _endpoint("SHORT_TERM_MEMORY", 18705),
                _endpoint("PLANNING_REASONING", 18712),
                _endpoint("INFERENCE_ENGINE", 18704),
            ),
        )


class FakeMemory:
    def __init__(self):
        self.committed = None

    async def prepare_context(self, **_kwargs):
        return PreparedContext((ContextMessage("user", "我在办理A公司授信"),), "req-memory")

    async def commit_turn(self, **kwargs):
        self.committed = kwargs
        return CommitResult(kwargs["turn_id"], False, 3)


class FakeInference:
    async def complete(self, **_kwargs):
        return InferenceResult(
            content='{"intent":"CHAT","answer":"你正在办理A公司授信。","skill":null}',
            provider="direct-provider",
            model="approved-model",
            input_tokens=20,
            output_tokens=10,
            request_id="req-model",
        )


class FakePlanning:
    async def invoke(self, **_kwargs):
        raise AssertionError("normal chat must not invoke planning")


@pytest.mark.asyncio
async def test_explicit_skill_creation_request_routes_to_planning_when_intent_model_misclassifies():
    class ClarifyingPlanning:
        async def invoke(self, **kwargs):
            assert kwargs["operation"] == "CONVERSE"
            return {
                "status": "CLARIFYING",
                "complexity": "SIMPLE",
                "draft": {"confirmedFacts": []},
                "questions": [{"question": "材料由谁提供？"}],
                "references": [],
                "decisionSummary": "已识别授信材料检查目标。",
            }

    agent = CustomerCoreComponentAgent(
        agent_id="core-component-demo-agent",
        service_credential="server-secret",
        genb=FakeGenB(),
        memory=FakeMemory(),
        inference=FakeInference(),
        planning=ClarifyingPlanning(),
    )

    result = await agent.chat(
        session_grant="server-only-session-grant",
        task_id="task-explicit-skill",
        session_id="session-explicit-skill",
        message="帮我生成一个用于银行对公授信材料检查的Skill。",
    )

    assert result.mode == "PLANNING_CLARIFICATION"
    assert "材料由谁提供" in result.answer


class FakePlanningReady:
    def __init__(self):
        self.operations = []

    async def invoke(self, **kwargs):
        self.operations.append(kwargs["operation"])
        if kwargs["operation"] == "CONVERSE":
            assert kwargs["payload"]["taskId"] == "task-plan"
            return {
                "status": "READY",
                "complexity": "SIMPLE",
                "draft": {
                    "name": "授信材料检查",
                    "description": "检查授信材料并输出缺失清单",
                    "goal": "检查授信材料",
                    "expectedInputs": ["申请表"],
                    "expectedOutputs": ["缺失清单"],
                    "constraints": ["不得修改原件"],
                    "preferredTools": [],
                    "toolReferences": [],
                    "riskLevel": "LOW",
                },
                "questions": [],
                "references": [],
                "decisionSummary": "需求已完整。",
            }
        return {
            "skillId": "skill-credit-check",
            "version": 1,
            "name": "credit-check",
            "skillMarkdown": "---\nname: credit-check\ndescription: 授信材料检查\n---\n",
            "validation": {"valid": True, "issues": []},
        }


@pytest.mark.asyncio
async def test_customer_agent_uses_three_bound_components_and_returns_natural_answer():
    genb = FakeGenB()
    memory = FakeMemory()
    agent = CustomerCoreComponentAgent(
        agent_id="core-component-demo-agent",
        service_credential="server-secret",
        genb=genb,
        memory=memory,
        inference=FakeInference(),
        planning=FakePlanning(),
    )

    result = await agent.chat(
        session_grant="server-only-session-grant",
        task_id="task-a",
        session_id="session-b",
        message="我在办理什么业务？",
    )

    assert genb.requested == ("SHORT_TERM_MEMORY", "PLANNING_REASONING", "INFERENCE_ENGINE")
    assert genb.session_grant == "server-only-session-grant"
    assert result.answer == "你正在办理A公司授信。"
    assert result.mode == "CHAT"
    assert result.diagnostics.model == "approved-model"
    assert result.diagnostics.context_message_count == 1
    assert memory.committed["assistant_message"] == result.answer


@pytest.mark.asyncio
async def test_customer_agent_automatically_generates_skill_for_complete_planning_request():
    planning = FakePlanningReady()

    class PlanningInference:
        async def complete(self, **_kwargs):
            return InferenceResult(
                content=(
                    '{"intent":"CREATE_SKILL","answer":"需求已完整。","skill":'
                    '{"name":"授信材料检查","description":"检查授信材料并输出缺失清单",'
                    '"goal":"检查授信材料","expectedInputs":["申请表"],'
                    '"expectedOutputs":["缺失清单"],"constraints":["不得修改原件"],'
                    '"riskLevel":"LOW","toolReferences":[]}}'
                ),
                provider="direct-provider",
                model="approved-model",
                input_tokens=30,
                output_tokens=40,
                request_id="req-planning-intent",
            )

    agent = CustomerCoreComponentAgent(
        agent_id="core-component-demo-agent",
        service_credential="server-secret",
        genb=FakeGenB(),
        memory=FakeMemory(),
        inference=PlanningInference(),
        planning=planning,
    )

    result = await agent.chat(
        session_grant="server-only-session-grant",
        task_id="task-plan",
        session_id="session-plan",
        message="生成授信材料检查Skill，输入为申请表，输出为缺失清单，约束是不得修改原件。",
    )

    assert planning.operations == ["CONVERSE", "GENERATE"]
    assert result.mode == "SKILL_GENERATED"
    assert result.skill["skillId"] == "skill-credit-check"
    assert "已经生成" in result.answer
    assert result.diagnostics.planning_operation == "GENERATE"


@pytest.mark.asyncio
async def test_customer_agent_does_not_accept_model_invented_requirements():
    class ClarifyingPlanning:
        async def invoke(self, **kwargs):
            assert kwargs["operation"] == "CONVERSE"
            assert kwargs["payload"]["message"] == "帮我生成一个审单Skill。"
            return {
                "status": "CLARIFYING",
                "complexity": "SIMPLE",
                "draft": {
                    "name": "审单",
                    "description": "自动检查审单材料是否齐全",
                    "goal": "检查材料",
                    "expectedInputs": [],
                    "expectedOutputs": [],
                    "constraints": [],
                    "preferredTools": [],
                    "toolReferences": [],
                    "riskLevel": "LOW",
                },
                "questions": [{"question": "这次要检查哪一类业务材料？"}],
                "references": [],
                "decisionSummary": "需要先确认业务类型。",
            }

    class InventingInference:
        async def complete(self, **_kwargs):
            return InferenceResult(
                content=(
                    '{"intent":"CREATE_SKILL","answer":"开始生成。","skill":'
                    '{"name":"审单","description":"自动检查审单材料是否齐全",'
                    '"goal":"检查材料","expectedInputs":["模型猜测的申请表"],'
                    '"expectedOutputs":["模型猜测的清单"],"constraints":["模型猜测的规则"],'
                    '"riskLevel":"LOW","toolReferences":[]}}'
                ),
                provider="direct-provider",
                model="approved-model",
                input_tokens=10,
                output_tokens=20,
                request_id="req-invented",
            )

    agent = CustomerCoreComponentAgent(
        agent_id="core-component-demo-agent",
        service_credential="server-secret",
        genb=FakeGenB(),
        memory=FakeMemory(),
        inference=InventingInference(),
        planning=ClarifyingPlanning(),
    )

    result = await agent.chat(
        session_grant="server-only-session-grant",
        task_id="task-incomplete",
        session_id="session-incomplete",
        message="帮我生成一个审单Skill。",
    )

    assert result.mode == "PLANNING_CLARIFICATION"
    assert "这次要检查哪一类业务材料" in result.answer
