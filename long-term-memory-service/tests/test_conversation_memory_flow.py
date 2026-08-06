from fastapi.testclient import TestClient

import long_term_memory.main as main_module
from long_term_memory.extraction import ExtractionCandidate, ExtractionModelResult
from long_term_memory.identity import InvocationIdentity
from long_term_memory.models import ExtractionRequest, SearchRequest
from long_term_memory.repository import InMemoryConversationMemoryRepository
from long_term_memory.service import LongTermMemoryService


class FakeExtractionModel:
    def extract(self, *, user_message: str, assistant_message: str) -> ExtractionModelResult:
        assert "13800138000" not in user_message
        assert assistant_message == "好的，之后将优先使用中文。"
        return ExtractionModelResult(
            model="memory-model-test",
            candidates=(
                ExtractionCandidate(
                    memory_type="USER_PREFERENCE",
                    content="用户偏好中文回答。",
                    confidence=0.95,
                ),
                ExtractionCandidate(
                    memory_type="STABLE_FACT",
                    content="用户的登录密码是 dangerous-secret。",
                    confidence=0.99,
                ),
                ExtractionCandidate(
                    memory_type="USER_CONSTRAINT",
                    content="用户暂时不需要提醒。",
                    confidence=0.5,
                ),
            ),
        )


def test_extracted_conversation_memory_is_filtered_and_searchable(monkeypatch) -> None:
    repository = InMemoryConversationMemoryRepository()
    service = LongTermMemoryService(repository, extraction_model=FakeExtractionModel())
    monkeypatch.setattr(main_module, "long_term_memory", service)
    headers = {
        "X-Tenant-Id": "tenant-flow-a",
        "X-Agent-Id": "agent-flow-a",
        "X-User-Id": "user-flow-a",
    }

    with TestClient(main_module.app) as client:
        accepted = client.post(
            "/api/v1/long-term-memory/extractions",
            headers={**headers, "Idempotency-Key": "flow-extraction-key-0001"},
            json={
                "conversationId": "conversation-flow-a",
                "turnId": "turn-flow-a",
                "userMessage": "我偏好中文回答，手机号是13800138000。",
                "assistantMessage": "好的，之后将优先使用中文。",
                "occurredAt": "2026-08-06T10:00:00Z",
            },
        )
        extraction_id = accepted.json()["data"]["extractionId"]
        status = client.get(
            f"/api/v1/long-term-memory/extractions/{extraction_id}",
            headers=headers,
        )
        search = client.post(
            "/api/v1/long-term-memory/memories:search",
            headers=headers,
            json={"query": "中文", "sourceTypes": ["CONVERSATION"]},
        )

    assert accepted.status_code == 202
    assert status.json()["data"]["status"] == "SUCCEEDED"
    assert status.json()["data"]["writtenCount"] == 1
    assert status.json()["data"]["rejectedCount"] == 2
    assert len(search.json()["data"]["items"]) == 1
    assert search.json()["data"]["items"][0]["sourceType"] == "CONVERSATION"
    assert search.json()["data"]["items"][0]["sourceRef"] == "turn-flow-a"
    assert "dangerous-secret" not in str(search.json())


def test_forgotten_conversation_memory_is_no_longer_recalled(monkeypatch) -> None:
    repository = InMemoryConversationMemoryRepository()
    service = LongTermMemoryService(repository, extraction_model=FakeExtractionModel())
    monkeypatch.setattr(main_module, "long_term_memory", service)
    headers = {
        "X-Tenant-Id": "tenant-forget-a",
        "X-Agent-Id": "agent-forget-a",
        "X-User-Id": "user-forget-a",
    }

    with TestClient(main_module.app) as client:
        client.post(
            "/api/v1/long-term-memory/extractions",
            headers={**headers, "Idempotency-Key": "forget-extraction-key-0001"},
            json={
                "conversationId": "conversation-forget-a",
                "turnId": "turn-forget-a",
                "userMessage": "我偏好中文回答，手机号是13800138000。",
                "assistantMessage": "好的，之后将优先使用中文。",
                "occurredAt": "2026-08-06T10:10:00Z",
            },
        )
        before = client.post(
            "/api/v1/long-term-memory/memories:search",
            headers=headers,
            json={"query": "中文", "sourceTypes": ["CONVERSATION"]},
        )
        memory_id = before.json()["data"]["items"][0]["memoryId"]
        forgotten = client.request(
            "DELETE",
            f"/api/v1/long-term-memory/memories/{memory_id}",
            headers=headers,
            json={"reason": "用户要求忘记该偏好"},
        )
        after = client.post(
            "/api/v1/long-term-memory/memories:search",
            headers=headers,
            json={"query": "中文", "sourceTypes": ["CONVERSATION"]},
        )

    assert forgotten.status_code == 200
    assert forgotten.json()["data"] == {"deleted": True}
    assert after.json()["data"]["items"] == []


def test_same_user_and_agent_recall_memory_across_component_sessions() -> None:
    repository = InMemoryConversationMemoryRepository()
    service = LongTermMemoryService(repository, extraction_model=FakeExtractionModel())
    first_session = InvocationIdentity(
        tenant_id="tenant-cross-session",
        agent_id="agent-cross-session",
        user_id="user-cross-session",
        session_id="session-one",
        token_type="DEVELOPMENT",
    )
    second_session = InvocationIdentity(
        tenant_id=first_session.tenant_id,
        agent_id=first_session.agent_id,
        user_id=first_session.user_id,
        session_id="session-two",
        token_type="DEVELOPMENT",
    )
    job, _ = service.request_extraction(
        first_session,
        ExtractionRequest(
            conversationId="conversation-cross-session-one",
            turnId="turn-cross-session-one",
            userMessage="我偏好中文回答，手机号是13800138000。",
            assistantMessage="好的，之后将优先使用中文。",
            occurredAt="2026-08-06T11:00:00Z",
        ),
        "cross-session-key-0001",
    )
    service.process_extraction(job.extraction_id)

    recalled = service.search(
        second_session,
        SearchRequest(query="中文", sourceTypes=["CONVERSATION"]),
    )

    assert len(recalled.items) == 1
    assert recalled.items[0].content == "用户偏好中文回答。"


def test_correcting_memory_supersedes_old_content_and_recalls_only_the_correction(
    monkeypatch,
) -> None:
    repository = InMemoryConversationMemoryRepository()
    scope = ("tenant-correct-a", "user-correct-a", "agent-correct-a")
    original = repository.upsert_memory(
        scope,
        ExtractionCandidate(
            memory_type="USER_PREFERENCE",
            content="用户偏好英文回答。",
            confidence=0.9,
        ),
        source_ref="turn-original",
        retention_days=180,
    )
    monkeypatch.setattr(
        main_module,
        "long_term_memory",
        LongTermMemoryService(repository),
    )
    headers = {
        "X-Tenant-Id": scope[0],
        "X-User-Id": scope[1],
        "X-Agent-Id": scope[2],
    }

    with TestClient(main_module.app) as client:
        corrected = client.post(
            f"/api/v1/long-term-memory/memories/{original.memory_id}:correct",
            headers=headers,
            json={"content": "用户偏好中文回答。", "reason": "用户主动更正"},
        )
        recalled = client.post(
            "/api/v1/long-term-memory/memories:search",
            headers=headers,
            json={"query": "", "sourceTypes": ["CONVERSATION"]},
        )

    assert corrected.status_code == 200
    assert corrected.json()["data"]["memoryId"] != original.memory_id
    assert [item["content"] for item in recalled.json()["data"]["items"]] == [
        "用户偏好中文回答。"
    ]


def test_feedback_confirmation_strengthens_memory_and_rejection_removes_it_from_recall(
    monkeypatch,
) -> None:
    repository = InMemoryConversationMemoryRepository()
    scope = ("tenant-feedback-a", "user-feedback-a", "agent-feedback-a")
    memory = repository.upsert_memory(
        scope,
        ExtractionCandidate(
            memory_type="USER_CONSTRAINT",
            content="用户只接受工作日联系。",
            confidence=0.9,
        ),
        source_ref="turn-feedback",
        retention_days=180,
    )
    monkeypatch.setattr(
        main_module,
        "long_term_memory",
        LongTermMemoryService(repository),
    )
    headers = {
        "X-Tenant-Id": scope[0],
        "X-User-Id": scope[1],
        "X-Agent-Id": scope[2],
    }

    with TestClient(main_module.app) as client:
        confirmed = client.post(
            f"/api/v1/long-term-memory/memories/{memory.memory_id}:feedback",
            headers=headers,
            json={"action": "CONFIRM", "reason": "用户确认仍然有效"},
        )
        rejected = client.post(
            f"/api/v1/long-term-memory/memories/{memory.memory_id}:feedback",
            headers=headers,
            json={"action": "REJECT", "reason": "用户表示不再适用"},
        )
        recalled = client.post(
            "/api/v1/long-term-memory/memories:search",
            headers=headers,
            json={"query": "工作日", "sourceTypes": ["CONVERSATION"]},
        )

    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["confidence"] > memory.confidence
    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == "SUPERSEDED"
    assert recalled.json()["data"]["items"] == []
