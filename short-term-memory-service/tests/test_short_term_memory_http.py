from fastapi.testclient import TestClient

from short_term_memory.main import app


HEADERS = {
    "X-Tenant-Id": "tenant-a",
    "X-Agent-Id": "agent-a",
    "X-User-Id": "user-a",
}


def test_task_context_recovers_across_sessions() -> None:
    with TestClient(app) as client:
        saved = client.put(
            "/api/v1/short-term-memory/tasks/task-001",
            headers=HEADERS,
            json={
                "status": "WAITING_MATERIAL",
                "instructions": ["优先核对营业执照"],
                "progress": "已完成基础信息检查",
                "pendingMaterials": ["近三个月流水"],
                "toolResults": [{"tool": "company-search", "summary": "企业状态正常"}],
                "resumeCheckpoint": "等待用户补充流水",
                "expiresInSeconds": 86400,
            },
        )
        assert saved.status_code == 200

        committed = client.post(
            "/api/v1/short-term-memory/turns:commit",
            headers={**HEADERS, "Idempotency-Key": "idem-task-001-turn-001"},
            json={
                "taskId": "task-001",
                "sessionId": "session-001",
                "turnId": "turn-001",
                "userMessage": "请先检查企业基本资料",
                "assistantMessage": "基础资料已经检查完成",
                "occurredAt": "2026-07-30T10:00:00Z",
            },
        )
        assert committed.status_code == 200

        prepared = client.post(
            "/api/v1/short-term-memory/context:prepare",
            headers=HEADERS,
            json={
                "taskId": "task-001",
                "sessionId": "session-002",
                "query": "继续办理",
                "maxMessages": 20,
            },
        )
        assert prepared.status_code == 200
        data = prepared.json()["data"]
        assert data["taskId"] == "task-001"
        assert data["sessionId"] == "session-002"
        assert data["workbench"]["status"] == "WAITING_MATERIAL"
        assert data["workbench"]["pendingMaterials"] == ["近三个月流水"]
        assert data["messages"] == [
            {
                "turnId": "turn-001",
                "sessionId": "session-001",
                "role": "user",
                "content": "请先检查企业基本资料",
                "occurredAt": "2026-07-30T10:00:00Z",
            },
            {
                "turnId": "turn-001",
                "sessionId": "session-001",
                "role": "assistant",
                "content": "基础资料已经检查完成",
                "occurredAt": "2026-07-30T10:00:00Z",
            },
        ]


def test_task_is_isolated_and_can_be_deleted() -> None:
    with TestClient(app) as client:
        created = client.put(
            "/api/v1/short-term-memory/tasks/task-isolated",
            headers=HEADERS,
            json={"status": "ACTIVE", "progress": "仅user-a可见", "expiresInSeconds": 3600},
        )
        assert created.status_code == 200

        visible = client.get("/api/v1/short-term-memory/tasks/task-isolated", headers=HEADERS)
        assert visible.status_code == 200
        assert visible.json()["data"]["workbench"]["progress"] == "仅user-a可见"

        hidden = client.get(
            "/api/v1/short-term-memory/tasks/task-isolated",
            headers={**HEADERS, "X-User-Id": "user-b"},
        )
        assert hidden.status_code == 404

        deleted = client.delete("/api/v1/short-term-memory/tasks/task-isolated", headers=HEADERS)
        assert deleted.status_code == 204
        assert client.get("/api/v1/short-term-memory/tasks/task-isolated", headers=HEADERS).status_code == 404


def test_sensitive_values_are_redacted_before_storage() -> None:
    with TestClient(app) as client:
        committed = client.post(
            "/api/v1/short-term-memory/turns:commit",
            headers={**HEADERS, "Idempotency-Key": "idem-sensitive-001"},
            json={
                "taskId": "task-sensitive",
                "sessionId": "session-sensitive",
                "turnId": "turn-sensitive",
                "userMessage": "password=secret123，验证码=998877",
                "assistantMessage": "token: abc.def.ghi",
                "occurredAt": "2026-07-30T10:05:00Z",
            },
        )
        assert committed.status_code == 200

        prepared = client.post(
            "/api/v1/short-term-memory/context:prepare",
            headers=HEADERS,
            json={"taskId": "task-sensitive", "sessionId": "session-new", "maxMessages": 10},
        )
        serialized = prepared.text
        assert "secret123" not in serialized
        assert "998877" not in serialized
        assert "abc.def.ghi" not in serialized
        assert "[REDACTED]" in serialized


def test_sensitive_values_are_also_redacted_from_task_workbench() -> None:
    with TestClient(app) as client:
        saved = client.put(
            "/api/v1/short-term-memory/tasks/task-sensitive-workbench",
            headers=HEADERS,
            json={
                "status": "ACTIVE",
                "instructions": ["使用 password=do-not-store 登录"],
                "progress": "token: private-token",
                "toolResults": [{"tool": "login", "summary": "验证码=123456"}],
                "expiresInSeconds": 3600,
            },
        )
        assert saved.status_code == 200
        serialized = saved.text
        assert "do-not-store" not in serialized
        assert "private-token" not in serialized
        assert "123456" not in serialized
        assert serialized.count("[REDACTED]") == 3


def test_turn_commit_is_idempotent_and_rejects_conflicting_reuse() -> None:
    payload = {
        "taskId": "task-idempotent",
        "sessionId": "session-idempotent",
        "turnId": "turn-idempotent",
        "userMessage": "第一条消息",
        "assistantMessage": "第一条回答",
        "occurredAt": "2026-07-30T10:10:00Z",
    }
    headers = {**HEADERS, "Idempotency-Key": "idem-idempotent-001"}
    with TestClient(app) as client:
        first = client.post("/api/v1/short-term-memory/turns:commit", headers=headers, json=payload)
        replay = client.post("/api/v1/short-term-memory/turns:commit", headers=headers, json=payload)
        conflict = client.post(
            "/api/v1/short-term-memory/turns:commit",
            headers=headers,
            json={**payload, "assistantMessage": "被修改的回答"},
        )

        assert first.status_code == 200
        assert replay.status_code == 200
        assert first.json()["data"]["messageCount"] == 2
        assert replay.json()["data"]["messageCount"] == 2
        assert replay.json()["data"]["replayed"] is True
        assert conflict.status_code == 409


def test_openapi_exposes_stable_multi_operation_contract() -> None:
    with TestClient(app) as client:
        document = client.get("/openapi.json").json()

    assert document["openapi"] == "3.1.0"
    operations = {
        operation["operationId"]
        for path in document["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "put", "delete"}
    }
    assert {
        "prepareShortTermContext",
        "commitShortTermTurn",
        "saveTaskWorkbench",
        "getTaskWorkbench",
        "deleteTaskWorkbench",
    }.issubset(operations)
    task_response_schema = document["paths"]["/api/v1/short-term-memory/tasks/{task_id}"]["put"]["responses"]["200"]["content"]["application/json"]["schema"]
    context_response_schema = document["paths"]["/api/v1/short-term-memory/context:prepare"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert task_response_schema["$ref"].endswith("/TaskWorkbenchResponse")
    assert context_response_schema["$ref"].endswith("/ContextPrepareResponse")
