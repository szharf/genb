from fastapi.testclient import TestClient

from long_term_memory.main import app


DEVELOPMENT_IDENTITY = {
    "X-Tenant-Id": "tenant-a",
    "X-Agent-Id": "agent-a",
    "X-User-Id": "user-a",
}


def test_service_reports_live() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


def test_service_reports_stable_component_version() -> None:
    with TestClient(app) as client:
        response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {
        "componentCode": "LONG_TERM_MEMORY",
        "implementationCode": "long-term-memory-service-v1",
        "interfaceVersion": "1.0.0",
        "serviceVersion": "0.1.0",
    }


def test_service_reports_ready_with_current_store() -> None:
    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "UP", "store": "IN_MEMORY"}


def test_extraction_rejects_missing_invocation_identity() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/long-term-memory/extractions",
            json={"conversationId": "conversation-a", "messages": []},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "开发身份Header不完整"}


def test_conversation_extraction_is_accepted_as_a_pending_job() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/long-term-memory/extractions",
            headers={
                **DEVELOPMENT_IDENTITY,
                "Idempotency-Key": "extraction-key-0001",
            },
            json={
                "conversationId": "conversation-a",
                "turnId": "turn-a",
                "userMessage": "我偏好中文回答，手机号是13800138000。",
                "assistantMessage": "好的，之后将优先使用中文。",
                "occurredAt": "2026-08-06T09:00:00Z",
            },
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["data"]["status"] == "PENDING"
    assert payload["data"]["duplicate"] is False
    assert isinstance(payload["data"]["extractionId"], str)
    assert payload["meta"] == {"componentCode": "LONG_TERM_MEMORY"}


def test_accepted_extraction_can_be_queried_by_the_same_identity() -> None:
    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/long-term-memory/extractions",
            headers={
                **DEVELOPMENT_IDENTITY,
                "Idempotency-Key": "query-extraction-key-0001",
            },
            json={
                "conversationId": "conversation-query-a",
                "turnId": "turn-query-a",
                "userMessage": "请记住我只接受工作日联系。",
                "assistantMessage": "已了解。",
                "occurredAt": "2026-08-06T09:10:00Z",
            },
        )
        extraction_id = accepted.json()["data"]["extractionId"]

        response = client.get(
            f"/api/v1/long-term-memory/extractions/{extraction_id}",
            headers=DEVELOPMENT_IDENTITY,
        )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "extractionId": extraction_id,
        "status": "PENDING",
        "attemptCount": 0,
        "writtenCount": 0,
        "rejectedCount": 0,
        "errorCode": None,
    }


def test_extraction_job_is_hidden_from_another_tenant() -> None:
    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/long-term-memory/extractions",
            headers={
                **DEVELOPMENT_IDENTITY,
                "Idempotency-Key": "isolated-extraction-0001",
            },
            json={
                "conversationId": "conversation-isolated-a",
                "turnId": "turn-isolated-a",
                "userMessage": "请记住本租户的采购偏好。",
                "assistantMessage": "已了解。",
                "occurredAt": "2026-08-06T09:20:00Z",
            },
        )
        extraction_id = accepted.json()["data"]["extractionId"]

        response = client.get(
            f"/api/v1/long-term-memory/extractions/{extraction_id}",
            headers={**DEVELOPMENT_IDENTITY, "X-Tenant-Id": "tenant-b"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "长期记忆提取任务不存在"}


def test_same_extraction_retry_returns_the_original_job() -> None:
    request = {
        "conversationId": "conversation-retry-a",
        "turnId": "turn-retry-a",
        "userMessage": "请记住发票需要月末汇总。",
        "assistantMessage": "已了解。",
        "occurredAt": "2026-08-06T09:30:00Z",
    }
    headers = {
        **DEVELOPMENT_IDENTITY,
        "Idempotency-Key": "retry-extraction-key-0001",
    }
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/long-term-memory/extractions", headers=headers, json=request
        )
        retried = client.post(
            "/api/v1/long-term-memory/extractions", headers=headers, json=request
        )

    assert first.status_code == 202
    assert retried.status_code == 202
    assert retried.json()["data"] == {
        "extractionId": first.json()["data"]["extractionId"],
        "status": "PENDING",
        "duplicate": True,
    }


def test_reusing_idempotency_key_for_different_content_is_rejected() -> None:
    headers = {
        **DEVELOPMENT_IDENTITY,
        "Idempotency-Key": "conflicting-key-0001",
    }
    request = {
        "conversationId": "conversation-conflict-a",
        "turnId": "turn-conflict-a",
        "userMessage": "请记住首选邮件联系。",
        "assistantMessage": "已了解。",
        "occurredAt": "2026-08-06T09:40:00Z",
    }
    with TestClient(app, raise_server_exceptions=False) as client:
        client.post(
            "/api/v1/long-term-memory/extractions", headers=headers, json=request
        )
        response = client.post(
            "/api/v1/long-term-memory/extractions",
            headers=headers,
            json={**request, "userMessage": "请改为首选电话联系。"},
        )

    assert response.status_code == 409
    assert response.json() == {"detail": "幂等键已用于不同的提取请求"}


def test_conversation_memory_search_has_an_explicit_empty_result_contract() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/long-term-memory/memories:search",
            headers=DEVELOPMENT_IDENTITY,
            json={
                "query": "尚未记录的偏好",
                "sourceTypes": ["CONVERSATION"],
                "topK": 5,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "data": {"items": [], "appliedTopK": 5},
        "meta": {"componentCode": "LONG_TERM_MEMORY"},
    }
