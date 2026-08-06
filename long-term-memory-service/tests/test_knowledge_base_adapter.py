from fastapi.testclient import TestClient

import long_term_memory.main as main_module
from long_term_memory.extraction import ExtractionCandidate
from long_term_memory.knowledge_base import (
    FakeKnowledgeBaseAdapter,
    KnowledgeBaseAccessRevoked,
    KnowledgeBasePermissionDenied,
    KnowledgeBaseTimeout,
)
from long_term_memory.repository import InMemoryConversationMemoryRepository
from long_term_memory.service import LongTermMemoryService


class ForbiddenKnowledgeBaseAdapter:
    def search(self, **_kwargs):
        raise KnowledgeBasePermissionDenied


class TimedOutKnowledgeBaseAdapter:
    def search(self, **_kwargs):
        raise KnowledgeBaseTimeout


class RevokedKnowledgeBaseAdapter:
    def search(self, **_kwargs):
        raise KnowledgeBaseAccessRevoked


def test_fake_knowledge_base_adapter_records_the_isolated_call_context() -> None:
    adapter = FakeKnowledgeBaseAdapter()

    result = adapter.search(
        tenant_id="tenant-kb-fake",
        agent_id="agent-kb-fake",
        user_id="user-kb-fake",
        query="授信规则",
        types=frozenset({"STABLE_FACT"}),
        limit=3,
    )

    assert result == []
    assert adapter.calls == [
        {
            "tenant_id": "tenant-kb-fake",
            "agent_id": "agent-kb-fake",
            "user_id": "user-kb-fake",
            "query": "授信规则",
            "types": frozenset({"STABLE_FACT"}),
            "limit": 3,
        }
    ]


def test_knowledge_base_only_search_does_not_fake_an_empty_result_when_unavailable() -> None:
    with TestClient(main_module.app) as client:
        response = client.post(
            "/api/v1/long-term-memory/memories:search",
            headers={
                "X-Tenant-Id": "tenant-kb-a",
                "X-Agent-Id": "agent-kb-a",
                "X-User-Id": "user-kb-a",
            },
            json={"query": "授信规则", "sourceTypes": ["KNOWLEDGE_BASE"]},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "知识库来源当前不可用"}


def test_mixed_search_returns_conversation_memory_and_marks_knowledge_base_degraded(
    monkeypatch,
) -> None:
    repository = InMemoryConversationMemoryRepository()
    repository.upsert_memory(
        ("tenant-kb-mixed", "user-kb-mixed", "agent-kb-mixed"),
        ExtractionCandidate(
            memory_type="USER_PREFERENCE",
            content="用户偏好中文回答。",
            confidence=0.95,
        ),
        source_ref="turn-kb-mixed",
        retention_days=180,
    )
    monkeypatch.setattr(
        main_module,
        "long_term_memory",
        LongTermMemoryService(repository),
    )

    with TestClient(main_module.app) as client:
        response = client.post(
            "/api/v1/long-term-memory/memories:search",
            headers={
                "X-Tenant-Id": "tenant-kb-mixed",
                "X-Agent-Id": "agent-kb-mixed",
                "X-User-Id": "user-kb-mixed",
            },
            json={
                "query": "中文",
                "sourceTypes": ["CONVERSATION", "KNOWLEDGE_BASE"],
            },
        )

    assert response.status_code == 200
    assert [item["sourceType"] for item in response.json()["data"]["items"]] == [
        "CONVERSATION"
    ]
    assert response.json()["meta"]["degradedSources"] == ["KNOWLEDGE_BASE"]


def test_knowledge_base_permission_denial_is_not_reported_as_no_results(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        main_module,
        "long_term_memory",
        LongTermMemoryService(
            InMemoryConversationMemoryRepository(),
            knowledge_base_adapter=ForbiddenKnowledgeBaseAdapter(),
        ),
    )

    with TestClient(main_module.app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/long-term-memory/memories:search",
            headers={
                "X-Tenant-Id": "tenant-kb-forbidden",
                "X-Agent-Id": "agent-kb-forbidden",
                "X-User-Id": "user-kb-forbidden",
            },
            json={"query": "内部授信规则", "sourceTypes": ["KNOWLEDGE_BASE"]},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "知识库来源无权访问"}


def test_knowledge_base_timeout_is_reported_as_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "long_term_memory",
        LongTermMemoryService(
            InMemoryConversationMemoryRepository(),
            knowledge_base_adapter=TimedOutKnowledgeBaseAdapter(),
        ),
    )
    with TestClient(main_module.app) as client:
        response = client.post(
            "/api/v1/long-term-memory/memories:search",
            headers={
                "X-Tenant-Id": "tenant-kb-timeout",
                "X-Agent-Id": "agent-kb-timeout",
                "X-User-Id": "user-kb-timeout",
            },
            json={"query": "授信规则", "sourceTypes": ["KNOWLEDGE_BASE"]},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "知识库来源当前不可用"}


def test_revoked_knowledge_base_cannot_leak_conversation_results(monkeypatch) -> None:
    repository = InMemoryConversationMemoryRepository()
    scope = ("tenant-kb-revoked", "user-kb-revoked", "agent-kb-revoked")
    repository.upsert_memory(
        scope,
        ExtractionCandidate(
            memory_type="STABLE_FACT",
            content="不应出现在撤权响应中的对话记忆。",
            confidence=0.95,
        ),
        source_ref="turn-revoked",
        retention_days=180,
    )
    monkeypatch.setattr(
        main_module,
        "long_term_memory",
        LongTermMemoryService(
            repository,
            knowledge_base_adapter=RevokedKnowledgeBaseAdapter(),
        ),
    )
    with TestClient(main_module.app) as client:
        response = client.post(
            "/api/v1/long-term-memory/memories:search",
            headers={
                "X-Tenant-Id": scope[0],
                "X-Agent-Id": scope[2],
                "X-User-Id": scope[1],
            },
            json={
                "query": "撤权",
                "sourceTypes": ["CONVERSATION", "KNOWLEDGE_BASE"],
            },
        )

    assert response.status_code == 403
    assert "对话记忆" not in response.text
