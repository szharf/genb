from datetime import UTC, datetime
import json

from fastapi.testclient import TestClient
import httpx
import pytest

from control_system.app import create_app
from control_system.component_config import (
    ShortTermMemoryRuntimeConfig,
    StaticShortTermMemoryConfigProvider,
)
from control_system.identity import InvocationIdentity, StaticIdentityVerifier
from control_system.short_term_memory.models import ConversationSummary, ConversationTurn
from control_system.short_term_memory.service import ShortTermMemoryService
from control_system.short_term_memory.store import InMemorySessionStore
from control_system.summary import (
    RuntimeInferenceSummaryGenerator,
    SummaryGenerationRequest,
    SummaryGenerationResult,
    SummaryMessage,
)
from control_system.telemetry import MetricsRegistry


class FakeSummaryGenerator:
    async def generate(
        self, request: SummaryGenerationRequest
    ) -> SummaryGenerationResult:
        assert request.capability == "SESSION_SUMMARY"
        return SummaryGenerationResult(
            summary="用户在连续讨论稳健型产品。",
            model="summary-model-test",
        )


class FailingSummaryGenerator:
    async def generate(self, request: SummaryGenerationRequest):
        del request
        raise RuntimeError("provider response must not escape")


def _identity() -> InvocationIdentity:
    return InvocationIdentity(
        tenant_id="tenant-sensitive",
        user_id="user-sensitive",
        agent_id="agent-sensitive",
        session_id="session-sensitive",
        service_credential_id="credential-a",
        allowed_components=frozenset({"SHORT_TERM_MEMORY"}),
        scopes=frozenset(
            {
                "component:short-term-memory:read",
                "component:short-term-memory:write",
            }
        ),
        request_id="req-summary-1",
    )


def _config() -> ShortTermMemoryRuntimeConfig:
    return ShortTermMemoryRuntimeConfig(
        ttl_seconds=600,
        max_turns=10,
        max_context_tokens=1000,
        summary_enabled=True,
        summary_trigger_turns=3,
        summary_model_alias="summary-default",
    )


async def _commit(memory: ShortTermMemoryService, identity: InvocationIdentity, number: int):
    await memory.commit_turn(
        identity,
        ConversationTurn(
            turn_id=f"turn-{number}",
            user_message=f"用户消息{number}",
            assistant_message=f"回答{number}",
            occurred_at=datetime(2026, 7, 24, number, tzinfo=UTC),
        ),
        f"summary-idempotency-{number}",
    )


@pytest.mark.asyncio
async def test_summary_covers_old_turns_and_prepare_avoids_duplicate_messages() -> None:
    store = InMemorySessionStore()
    metrics = MetricsRegistry()
    memory = ShortTermMemoryService(
        store,
        config_provider=StaticShortTermMemoryConfigProvider(_config()),
        summary_generator=FakeSummaryGenerator(),
        metrics=metrics,
    )
    identity = _identity()
    for number in (1, 2, 3):
        await _commit(memory, identity, number)

    status = await memory.refresh_summary_if_needed(identity)
    prepared = await memory.prepare_context(identity, max_context_tokens=1000)

    assert status == "SUCCESS"
    assert prepared.summary is not None
    assert prepared.summary.through_turn_id == "turn-2"
    assert prepared.summary.summary == "用户在连续讨论稳健型产品。"
    assert [message.turn_id for message in prepared.messages] == ["turn-3", "turn-3"]
    assert metrics.value("short_term_summary_total", {"result": "success"}) == 1


@pytest.mark.asyncio
async def test_summary_failure_is_degraded_and_keeps_recent_window() -> None:
    store = InMemorySessionStore()
    memory = ShortTermMemoryService(
        store,
        config_provider=StaticShortTermMemoryConfigProvider(_config()),
        summary_generator=FailingSummaryGenerator(),
    )
    identity = _identity()
    for number in (1, 2, 3):
        await _commit(memory, identity, number)

    status = await memory.refresh_summary_if_needed(identity)
    prepared = await memory.prepare_context(identity, max_context_tokens=1000)

    assert status == "DEGRADED"
    assert prepared.summary is None
    assert len(prepared.messages) == 6


def test_metrics_are_low_cardinality_and_do_not_expose_identity_or_content() -> None:
    identity = _identity()
    app = create_app(
        identity_verifier=StaticIdentityVerifier(
            credentials={("service-token-a", "actor-token-a"): identity}
        ),
        session_store=InMemorySessionStore(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers={
                "Authorization": "Bearer service-token-a",
                "X-GenB-Actor-Token": "actor-token-a",
            },
            json={"query": "private message", "maxContextTokens": 100},
        )
        metrics = client.get("/metrics")

    assert response.status_code == 200
    assert metrics.status_code == 200
    assert "control_system_http_requests_total" in metrics.text
    assert "short_term_context_hits_total" in metrics.text
    for forbidden in (
        "tenant-sensitive",
        "user-sensitive",
        "agent-sensitive",
        "session-sensitive",
        "private message",
        "service-token-a",
        "actor-token-a",
    ):
        assert forbidden not in metrics.text


@pytest.mark.asyncio
async def test_runtime_summary_adapter_uses_own_inference_interface_and_redacts_errors() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        captured["request_id"] = request.headers["x-request-id"]
        captured["trace_parent"] = request.headers["traceparent"]
        captured["payload"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "data": {
                    "content": "安全摘要",
                    "structured": None,
                    "modelAlias": "summary-default",
                    "model": "approved-model",
                    "provider": "direct-primary",
                    "usage": {
                        "inputTokens": 10,
                        "outputTokens": 4,
                        "totalTokens": 14,
                        "estimated": False,
                    },
                    "finishReason": "stop",
                },
                "meta": {},
            },
        )

    client = httpx.AsyncClient(
        base_url="http://runtime.local", transport=httpx.MockTransport(handler)
    )
    adapter = RuntimeInferenceSummaryGenerator(
        client=client,
        service_token="runtime-token-value",
    )
    result = await adapter.generate(
        SummaryGenerationRequest(
            messages=(SummaryMessage("turn-1", "user", "visible content"),),
            previous_summary=None,
            model_alias="summary-default",
            request_id="req-runtime-summary",
            trace_parent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        )
    )
    await client.aclose()

    assert result == SummaryGenerationResult("安全摘要", "approved-model")
    assert captured["authorization"] == "Bearer runtime-token-value"
    assert captured["request_id"] == "req-runtime-summary"
    assert captured["trace_parent"] == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    assert json.loads(str(captured["payload"]))["capability"] == "SESSION_SUMMARY"


@pytest.mark.asyncio
async def test_store_rejects_stale_summary_overwrite() -> None:
    store = InMemorySessionStore()
    scope = ("tenant", "user", "agent", "session")
    first = ConversationSummary(
        "first", "turn-2", "model-a", datetime(2026, 7, 24, tzinfo=UTC)
    )
    stale = ConversationSummary(
        "stale", "turn-1", "model-b", datetime(2026, 7, 24, 1, tzinfo=UTC)
    )

    assert await store.write_summary(
        scope, first, expected_through_turn_id=None, ttl_seconds=60
    )
    assert not await store.write_summary(
        scope, stale, expected_through_turn_id=None, ttl_seconds=60
    )
    assert await store.read_summary(scope) == first
