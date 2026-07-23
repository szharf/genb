from dataclasses import replace

from fastapi.testclient import TestClient
import httpx
import pytest

from control_system.app import create_app
from control_system.identity import InvocationIdentity, StaticIdentityVerifier
from control_system.long_term_memory.config import (
    LongTermMemoryRuntimeConfig,
    StaticLongTermMemoryConfigProvider,
)
from control_system.long_term_memory.extraction import (
    ExtractionCandidate,
    ExtractionModelResult,
    ExtractionModelRequest,
    RuntimeInferenceExtractionModel,
)
from control_system.long_term_memory.repository import InMemoryLongTermMemoryRepository
from control_system.short_term_memory.store import InMemorySessionStore


class FakeExtractionModel:
    async def extract(self, request):
        assert request.capability == "MEMORY_EXTRACTION"
        return ExtractionModelResult(
            model="memory-model-test",
            candidates=(
                ExtractionCandidate(
                    memory_type="USER_PREFERENCE",
                    content="用户偏好稳健、低波动的产品。",
                    confidence=0.95,
                    action="UPSERT",
                ),
                ExtractionCandidate(
                    memory_type="STABLE_FACT",
                    content="用户的登录密码是 dangerous-secret。",
                    confidence=0.99,
                    action="UPSERT",
                ),
                ExtractionCandidate(
                    memory_type="USER_CONSTRAINT",
                    content="用户暂时不需要提醒。",
                    confidence=0.5,
                    action="UPSERT",
                ),
            ),
        )


def _identity(user_id: str = "user-a", agent_id: str = "agent-a") -> InvocationIdentity:
    return InvocationIdentity(
        tenant_id="tenant-a",
        user_id=user_id,
        agent_id=agent_id,
        session_id="session-a",
        service_credential_id="credential-a",
        allowed_components=frozenset({"LONG_TERM_MEMORY"}),
        scopes=frozenset(
            {
                "component:long-term-memory:read",
                "component:long-term-memory:write",
                "component:long-term-memory:delete",
            }
        ),
        request_id="fixture-request",
        component_config_versions=(("LONG_TERM_MEMORY", 71),),
    )


def _app():
    identity_a = _identity()
    identity_b = _identity(user_id="user-b")
    repository = InMemoryLongTermMemoryRepository()
    config = LongTermMemoryRuntimeConfig(
        enabled_types=frozenset(
            {"USER_PREFERENCE", "STABLE_FACT", "USER_CONSTRAINT"}
        ),
        auto_extraction_enabled=True,
        confidence_threshold=0.8,
        retention_days=180,
        top_k=5,
        max_top_k=20,
        model_alias="memory-extraction-default",
        max_attempts=3,
    )
    app = create_app(
        identity_verifier=StaticIdentityVerifier(
            credentials={
                ("service-a", "actor-a"): identity_a,
                ("service-b", "actor-b"): identity_b,
            }
        ),
        session_store=InMemorySessionStore(),
        long_term_repository=repository,
        long_term_config_provider=StaticLongTermMemoryConfigProvider(config),
        extraction_model=FakeExtractionModel(),
        process_extractions_inline=True,
    )
    return app, repository


def _headers(service: str = "service-a", actor: str = "actor-a") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {service}",
        "X-GenB-Actor-Token": actor,
        "X-Request-Id": "req-long-term-test",
        "Idempotency-Key": "long-term-idempotency-0001",
    }


def test_extraction_is_reliable_idempotent_filtered_and_searchable() -> None:
    app, _repository = _app()
    request = {
        "turnId": "turn-long-1",
        "userMessage": "我长期偏好稳健低波动的产品",
        "assistantMessage": "好的，以后优先按稳健偏好推荐。",
        "occurredAt": "2026-07-24T01:00:00Z",
    }
    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/control-system/long-term-memory/extractions",
            headers=_headers(),
            json=request,
        )
        duplicate = client.post(
            "/api/v1/control-system/long-term-memory/extractions",
            headers=_headers(),
            json=request,
        )
        status = client.get(
            f"/api/v1/control-system/long-term-memory/extractions/{accepted.json()['data']['extractionId']}",
            headers={k: v for k, v in _headers().items() if k != "Idempotency-Key"},
        )
        search = client.post(
            "/api/v1/control-system/long-term-memory/search",
            headers={k: v for k, v in _headers().items() if k != "Idempotency-Key"},
            json={"query": "稳健", "types": ["USER_PREFERENCE"], "topK": 10},
        )
        memory_id = search.json()["data"]["items"][0]["memoryId"]
        deleted = client.post(
            f"/api/v1/control-system/long-term-memory/memories/{memory_id}:delete",
            headers={k: v for k, v in _headers().items() if k != "Idempotency-Key"},
            json={"reason": "user requested deletion"},
        )
        deleted_again = client.post(
            f"/api/v1/control-system/long-term-memory/memories/{memory_id}:delete",
            headers={k: v for k, v in _headers().items() if k != "Idempotency-Key"},
            json={"reason": "idempotent retry"},
        )
        after_delete = client.post(
            "/api/v1/control-system/long-term-memory/search",
            headers={k: v for k, v in _headers().items() if k != "Idempotency-Key"},
            json={"query": "稳健"},
        )

    assert accepted.status_code == 202
    assert accepted.json()["data"]["duplicate"] is False
    assert duplicate.status_code == 202
    assert duplicate.json()["data"]["duplicate"] is True
    assert duplicate.json()["data"]["extractionId"] == accepted.json()["data"]["extractionId"]
    assert status.status_code == 200
    assert status.json()["data"]["status"] == "SUCCEEDED"
    assert status.json()["data"]["writtenCount"] == 1
    assert status.json()["data"]["rejectedCount"] == 2
    assert search.status_code == 200
    assert len(search.json()["data"]["items"]) == 1
    assert search.json()["data"]["items"][0]["type"] == "USER_PREFERENCE"
    assert "password" not in str(search.json()).lower()
    assert "dangerous-secret" not in str(search.json())
    assert deleted.status_code == 200 and deleted.json()["data"]["deleted"] is True
    assert deleted_again.status_code == 200 and deleted_again.json()["data"]["deleted"] is False
    assert after_delete.json()["data"]["items"] == []


def test_long_term_memory_isolation_conflict_and_scope_are_fail_closed() -> None:
    app, _repository = _app()
    request = {
        "turnId": "turn-long-2",
        "userMessage": "我长期偏好稳健低波动的产品",
        "assistantMessage": "已记录。",
        "occurredAt": "2026-07-24T01:00:00Z",
    }
    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/control-system/long-term-memory/extractions",
            headers=_headers(),
            json=request,
        )
        conflict = client.post(
            "/api/v1/control-system/long-term-memory/extractions",
            headers=_headers(),
            json={**request, "userMessage": "different content"},
        )
        other_user_search = client.post(
            "/api/v1/control-system/long-term-memory/search",
            headers={
                "Authorization": "Bearer service-b",
                "X-GenB-Actor-Token": "actor-b",
            },
            json={"query": "稳健", "topK": 5},
        )
        other_user_status = client.get(
            f"/api/v1/control-system/long-term-memory/extractions/{accepted.json()['data']['extractionId']}",
            headers={
                "Authorization": "Bearer service-b",
                "X-GenB-Actor-Token": "actor-b",
            },
        )
        missing_scope_identity = replace(
            _identity(), scopes=frozenset({"component:long-term-memory:read"})
        )
        no_write_app = create_app(
            identity_verifier=StaticIdentityVerifier(
                credentials={("read-only", "actor-read"): missing_scope_identity}
            ),
            session_store=InMemorySessionStore(),
            long_term_repository=InMemoryLongTermMemoryRepository(),
        )
        with TestClient(no_write_app) as no_write_client:
            denied = no_write_client.post(
                "/api/v1/control-system/long-term-memory/extractions",
                headers={
                    "Authorization": "Bearer read-only",
                    "X-GenB-Actor-Token": "actor-read",
                    "Idempotency-Key": "long-term-read-only-key",
                },
                json=request,
            )

    assert accepted.status_code == 202
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "LONG_TERM_IDEMPOTENCY_CONFLICT"
    assert other_user_search.status_code == 200
    assert other_user_search.json()["data"]["items"] == []
    assert other_user_status.status_code == 404
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_runtime_extraction_adapter_uses_strict_structured_interface() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "data": {
                    "content": '{"memories":[]}',
                    "structured": {
                        "memories": [
                            {
                                "type": "USER_PREFERENCE",
                                "content": "用户偏好稳健产品。",
                                "confidence": 0.91,
                                "action": "UPSERT",
                            }
                        ]
                    },
                    "modelAlias": "memory-extraction-default",
                    "model": "approved-model",
                    "provider": "direct-primary",
                    "usage": {},
                    "finishReason": "stop",
                },
                "meta": {},
            },
        )

    client = httpx.AsyncClient(
        base_url="http://runtime.local", transport=httpx.MockTransport(handler)
    )
    adapter = RuntimeInferenceExtractionModel(
        client=client, service_token="runtime-extraction-token"
    )
    result = await adapter.extract(
        ExtractionModelRequest(
            user_message="我偏好稳健产品",
            assistant_message="已记录",
            model_alias="memory-extraction-default",
            request_id="req-extraction-adapter",
        )
    )
    await client.aclose()

    assert result.model == "approved-model"
    assert result.candidates[0].memory_type == "USER_PREFERENCE"
    assert captured["authorization"] == "Bearer runtime-extraction-token"
    assert '"capability":"MEMORY_EXTRACTION"' in str(captured["payload"]).replace(" ", "")
    assert '"responseFormat"' in str(captured["payload"])
