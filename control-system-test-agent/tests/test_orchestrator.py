from dataclasses import dataclass

import pytest

from control_system_test_agent.errors import RemoteCallError
from control_system_test_agent.models import (
    ActorSession,
    CommitResult,
    ComponentEndpoint,
    ContextMessage,
    ExtractionStatus,
    LongTermMemoryItem,
    PreparedContext,
)
from control_system_test_agent.orchestrator import DeterministicAnswerer, PlanningTestAgent, StandaloneMemoryTestAgent, TestAgent


@dataclass
class FakeGenB:
    agent_id: str

    async def issue_component_session(self, **kwargs: object) -> ActorSession:
        assert kwargs["agent_id"] == self.agent_id
        return ActorSession(
            component_session_id=f"component-{self.agent_id}",
            actor_token=f"actor-{self.agent_id}",
            expires_at="2026-07-23T12:00:00Z",
            components=(
                ComponentEndpoint(
                    component_code="SHORT_TERM_MEMORY",
                    implementation_code="control-memory-v1",
                    base_url="http://control.local",
                    interface_version="1.0.0",
                    config_version_id=7,
                    scopes=(
                        "component:short-term-memory:read",
                        "component:short-term-memory:write",
                    ),
                ),
            ),
        )


class FakeControl:
    def __init__(self, context: tuple[ContextMessage, ...] = ()) -> None:
        self.context = context
        self.commits: list[dict[str, object]] = []

    async def prepare_context(self, **_kwargs: object) -> PreparedContext:
        return PreparedContext(messages=self.context, request_id="req-prepare")

    async def commit_turn(self, **kwargs: object) -> CommitResult:
        self.commits.append(kwargs)
        return CommitResult(turn_id=str(kwargs["turn_id"]), duplicate=False, message_count=2)


@pytest.mark.asyncio
async def test_one_code_artifact_runs_two_logical_agents_without_state_sharing() -> None:
    control_a = FakeControl(
        (ContextMessage(role="user", content="A likes low risk", turn_id="turn-old"),)
    )
    control_b = FakeControl()
    agent_a = TestAgent(
        agent_id="memory-test-a",
        service_credential="credential-a",
        genb=FakeGenB("memory-test-a"),
        control=control_a,
        answerer=DeterministicAnswerer(),
    )
    agent_b = TestAgent(
        agent_id="memory-test-b",
        service_credential="credential-b",
        genb=FakeGenB("memory-test-b"),
        control=control_b,
        answerer=DeterministicAnswerer(),
    )

    result_a = await agent_a.chat(
        user_token="user-token",
        session_id="session-a",
        message="my preference?",
    )
    result_b = await agent_b.chat(
        user_token="user-token",
        session_id="session-a",
        message="my preference?",
    )

    assert result_a.context_message_count == 1
    assert result_b.context_message_count == 0
    assert control_a.commits[0]["service_credential"] == "credential-a"
    assert control_b.commits[0]["service_credential"] == "credential-b"


@pytest.mark.asyncio
async def test_prepare_failure_degrades_but_commit_failure_is_reported_without_losing_answer() -> None:
    class FailingControl(FakeControl):
        async def prepare_context(self, **_kwargs: object) -> PreparedContext:
            raise RemoteCallError(operation="prepare context", status_code=503, request_id="req-p")

        async def commit_turn(self, **_kwargs: object) -> CommitResult:
            raise RemoteCallError(operation="commit turn", status_code=503, request_id="req-c")

    agent = TestAgent(
        agent_id="memory-test-a",
        service_credential="credential-a",
        genb=FakeGenB("memory-test-a"),
        control=FailingControl(),
        answerer=DeterministicAnswerer(),
    )

    result = await agent.chat(
        user_token="user-token",
        session_id="session-a",
        message="hello",
    )

    assert result.answer
    assert result.context_message_count == 0
    assert result.committed is False
    assert result.warnings == ("SHORT_TERM_PREPARE_UNAVAILABLE", "SHORT_TERM_COMMIT_UNAVAILABLE")


class FakeStandaloneMemory:
    def __init__(self) -> None:
        self.prepares: list[dict[str, object]] = []
        self.commits: list[dict[str, object]] = []

    async def prepare_context(self, **kwargs: object) -> PreparedContext:
        self.prepares.append(kwargs)
        return PreparedContext(
            messages=(ContextMessage(role="user", content="first turn", turn_id="turn-old"),),
            request_id="req-prepare",
        )

    async def commit_turn(self, **kwargs: object) -> CommitResult:
        self.commits.append(kwargs)
        return CommitResult(turn_id=str(kwargs["turn_id"]), duplicate=False, message_count=4)


@pytest.mark.asyncio
async def test_standalone_agent_uses_genb_binding_endpoint_and_commits_same_task() -> None:
    memory = FakeStandaloneMemory()
    agent = StandaloneMemoryTestAgent(
        agent_id="standalone-memory-test-agent",
        service_credential="credential-a",
        genb=FakeGenB("standalone-memory-test-agent"),
        memory=memory,
        control=FakeControl(),
        answerer=DeterministicAnswerer(),
    )

    result = await agent.chat(
        user_token="user-token", task_id="task-a", session_id="session-a", message="second turn"
    )

    assert result.context_message_count == 1 and result.committed is True
    assert memory.prepares[0]["base_url"] == "http://control.local"
    assert memory.prepares[0]["task_id"] == "task-a"
    assert memory.commits[0]["task_id"] == "task-a"
    assert memory.commits[0]["session_id"] == "session-a"


@pytest.mark.asyncio
async def test_standalone_short_term_test_accepts_server_side_session_grant() -> None:
    class SessionGrantGenB(FakeGenB):
        async def issue_component_session(self, **kwargs: object) -> ActorSession:
            assert kwargs["session_grant"] == "server-only-session-grant"
            assert kwargs.get("user_token") is None
            assert kwargs["requested_components"] == ("SHORT_TERM_MEMORY",)
            return await super().issue_component_session(**kwargs)

    memory = FakeStandaloneMemory()
    agent = StandaloneMemoryTestAgent(
        agent_id="standalone-memory-test-agent",
        service_credential="credential-a",
        genb=SessionGrantGenB("standalone-memory-test-agent"),
        memory=memory,
        control=FakeControl(),
        answerer=DeterministicAnswerer(),
    )

    result = await agent.chat(
        session_grant="server-only-session-grant",
        task_id="task-a",
        session_id="session-a",
        message="first turn",
    )

    assert result.committed is True


@pytest.mark.asyncio
async def test_long_term_test_uses_its_own_binding_and_source_filter() -> None:
    class LongTermGenB(FakeGenB):
        async def issue_component_session(self, **kwargs: object) -> ActorSession:
            assert kwargs["session_grant"] == "server-only-session-grant"
            assert kwargs["requested_components"] == ("LONG_TERM_MEMORY",)
            return ActorSession(
                component_session_id="component-long", actor_token="actor-long",
                expires_at="2026-08-03T12:00:00Z",
                components=(ComponentEndpoint(
                    component_code="LONG_TERM_MEMORY", implementation_code="control-memory-v1",
                    base_url="http://control.local", interface_version="1.0.0",
                    config_version_id=8, scopes=("component:long-term-memory:read",),
                ),),
            )

    class LongTermControl(FakeControl):
        async def request_long_term_extraction(self, **kwargs: object) -> str:
            assert kwargs["actor_token"] == "actor-long"
            assert kwargs["base_url"] == "http://control.local"
            assert kwargs["conversation_id"] == "session-a"
            return "ext-a"

        async def get_long_term_extraction(self, **kwargs: object) -> ExtractionStatus:
            assert kwargs["base_url"] == "http://control.local"
            return ExtractionStatus("ext-a", "SUCCEEDED", 1, 0)

        async def search_long_term_memory(self, **kwargs: object) -> tuple[LongTermMemoryItem, ...]:
            assert kwargs["source_types"] == ("CONVERSATION",)
            assert kwargs["base_url"] == "http://control.local"
            return (LongTermMemoryItem(
                memory_id="mem-a", memory_type="USER_PREFERENCE", content="偏好稳健",
                confidence=0.95, source_type="CONVERSATION", source_ref="turn-a",
            ),)

    control = LongTermControl()
    agent = StandaloneMemoryTestAgent(
        agent_id="standalone-memory-test-agent", service_credential="credential-a",
        genb=LongTermGenB("standalone-memory-test-agent"), memory=FakeStandaloneMemory(),
        control=control, answerer=DeterministicAnswerer(),
    )

    extracted = await agent.store_long_term(
        session_grant="server-only-session-grant", session_id="session-a", message="偏好稳健"
    )
    recalled = await agent.recall_long_term(
        session_grant="server-only-session-grant", session_id="session-b", query="稳健",
        source_types=("CONVERSATION",),
    )

    assert extracted.status == "SUCCEEDED"
    assert recalled[0].source_type == "CONVERSATION"


@pytest.mark.asyncio
async def test_long_term_extraction_allows_real_model_processing_time(monkeypatch) -> None:
    class LongTermGenB(FakeGenB):
        async def issue_component_session(self, **_kwargs: object) -> ActorSession:
            return ActorSession(
                component_session_id="component-long", actor_token="actor-long",
                expires_at="2026-08-03T12:00:00Z",
                components=(ComponentEndpoint(
                    component_code="LONG_TERM_MEMORY", implementation_code="control-memory-v1",
                    base_url="http://control.local", interface_version="1.0.0",
                    config_version_id=8, scopes=("component:long-term-memory:write",),
                ),),
            )

    class SlowLongTermControl(FakeControl):
        def __init__(self) -> None:
            super().__init__()
            self.polls = 0

        async def request_long_term_extraction(self, **_kwargs: object) -> str:
            return "ext-slow"

        async def get_long_term_extraction(self, **_kwargs: object) -> ExtractionStatus:
            self.polls += 1
            if self.polls <= 30:
                return ExtractionStatus("ext-slow", "RUNNING", 0, 0)
            return ExtractionStatus("ext-slow", "SUCCEEDED", 1, 0)

    async def no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr("control_system_test_agent.orchestrator.asyncio.sleep", no_wait)
    control = SlowLongTermControl()
    agent = StandaloneMemoryTestAgent(
        agent_id="standalone-memory-test-agent", service_credential="credential-a",
        genb=LongTermGenB("standalone-memory-test-agent"), memory=FakeStandaloneMemory(),
        control=control, answerer=DeterministicAnswerer(),
    )

    result = await agent.store_long_term(
        session_grant="server-only-session-grant", session_id="session-a", message="偏好稳健"
    )

    assert result.status == "SUCCEEDED"
    assert control.polls == 31


class FakePlanning:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def invoke(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {"status": "READY", "questions": []}


@pytest.mark.asyncio
async def test_planning_agent_resolves_genb_binding_before_calling_service() -> None:
    class PlanningGenB(FakeGenB):
        async def issue_component_session(self, **kwargs: object) -> ActorSession:
            assert kwargs["requested_components"] == ("PLANNING_REASONING",)
            return ActorSession(
                component_session_id="component-plan", actor_token="actor-plan",
                expires_at="2026-07-30T12:00:00Z",
                components=(ComponentEndpoint(
                    component_code="PLANNING_REASONING", implementation_code="planning-v1",
                    base_url="http://planning.local", interface_version="1.0.0",
                    config_version_id=9, scopes=("component:planning-reasoning:invoke",),
                ),),
            )

    planning = FakePlanning()
    agent = PlanningTestAgent(
        agent_id="standalone-planning-test-agent", service_credential="credential-plan",
        genb=PlanningGenB("standalone-planning-test-agent"), planning=planning,
    )

    result = await agent.invoke(
        user_token="user-token", session_id="session-plan", operation="ANALYZE",
        payload={"goal": "生成授信检查Skill"},
    )

    assert result["status"] == "READY"
    assert planning.calls[0]["base_url"] == "http://planning.local"
    assert planning.calls[0]["actor_token"] == "actor-plan"


@pytest.mark.asyncio
async def test_planning_agent_accepts_server_side_session_grant() -> None:
    class PlanningGenB(FakeGenB):
        async def issue_component_session(self, **kwargs: object) -> ActorSession:
            assert kwargs["session_grant"] == "server-only-session-grant"
            assert kwargs.get("user_token") is None
            assert kwargs["requested_components"] == ("PLANNING_REASONING",)
            return ActorSession(
                component_session_id="component-plan", actor_token="actor-plan",
                expires_at="2026-08-03T12:00:00Z",
                components=(ComponentEndpoint(
                    component_code="PLANNING_REASONING", implementation_code="planning-v1",
                    base_url="http://planning.local", interface_version="1.0.0",
                    config_version_id=9, scopes=("component:planning-reasoning:invoke",),
                ),),
            )

    planning = FakePlanning()
    agent = PlanningTestAgent(
        agent_id="standalone-planning-test-agent", service_credential="credential-plan",
        genb=PlanningGenB("standalone-planning-test-agent"), planning=planning,
    )

    result = await agent.invoke(
        session_grant="server-only-session-grant", session_id="session-plan",
        operation="ANALYZE", payload={"goal": "生成授信检查Skill"},
    )

    assert result["status"] == "READY"
