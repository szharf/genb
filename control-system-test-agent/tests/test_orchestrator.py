from dataclasses import dataclass

import pytest

from control_system_test_agent.errors import RemoteCallError
from control_system_test_agent.models import (
    ActorSession,
    CommitResult,
    ComponentEndpoint,
    ContextMessage,
    PreparedContext,
)
from control_system_test_agent.orchestrator import DeterministicAnswerer, TestAgent


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
