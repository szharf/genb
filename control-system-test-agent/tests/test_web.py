from dataclasses import dataclass

from fastapi.testclient import TestClient

from control_system_test_agent.models import ChatResult, CustomerChatResult, CustomerDiagnostics
from control_system_test_agent.web import create_app, get_agent, get_customer_agent, get_planning_agent


@dataclass
class FakeAgent:
    calls: list[dict[str, str]]

    async def chat(self, **kwargs: str) -> ChatResult:
        self.calls.append(kwargs)
        return ChatResult(
            answer="测试回答（已读取2条上下文）：继续",
            context_message_count=2,
            committed=True,
            warnings=(),
        )


def test_chat_api_uses_request_user_token_without_exposing_service_credential(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "standalone-memory-test-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    fake = FakeAgent([])
    application = create_app()
    application.dependency_overrides[get_agent] = lambda: fake

    with TestClient(application) as client:
        response = client.post(
            "/api/chat",
            headers={"Authorization": "Bearer user-token-a"},
            json={"taskId": "task-a", "sessionId": "session-a", "message": "继续"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["contextMessageCount"] == 2
    assert fake.calls[0]["user_token"] == "user-token-a"
    assert "server-only-secret" not in response.text


def test_chat_api_rejects_missing_user_token(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "standalone-memory-test-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    application = create_app()
    application.dependency_overrides[get_agent] = lambda: FakeAgent([])

    with TestClient(application) as client:
        response = client.post(
            "/api/chat",
            json={"taskId": "task-a", "sessionId": "session-a", "message": "继续"},
        )

    assert response.status_code == 401


@dataclass
class FakePlanningAgent:
    calls: list[dict[str, object]]

    async def invoke(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {"status": "READY", "questions": []}


def test_planning_api_uses_user_token_and_returns_service_result(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "standalone-planning-test-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    fake = FakePlanningAgent([])
    application = create_app()
    application.dependency_overrides[get_planning_agent] = lambda: fake

    with TestClient(application) as client:
        response = client.post(
            "/api/planning",
            headers={"Authorization": "Bearer user-token-a"},
            json={
                "sessionId": "session-plan", "operation": "ANALYZE",
                "payload": {"goal": "生成授信检查Skill"},
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "READY"
    assert fake.calls[0]["user_token"] == "user-token-a"
    assert "server-only-secret" not in response.text


def test_planning_api_maps_invalid_operation_payload_to_bad_request(monkeypatch) -> None:
    class InvalidPlanningAgent:
        async def invoke(self, **_kwargs: object) -> dict[str, object]:
            raise ValueError("REVISE requires skillId")

    monkeypatch.setenv("AGENT_ID", "standalone-planning-test-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    application = create_app()
    application.dependency_overrides[get_planning_agent] = lambda: InvalidPlanningAgent()
    with TestClient(application) as client:
        response = client.post(
            "/api/planning", headers={"Authorization": "Bearer user-token-a"},
            json={"sessionId": "session-plan", "operation": "REVISE", "payload": {}},
        )
    assert response.status_code == 400


@dataclass
class FakeCustomerAgent:
    calls: list[dict[str, str]]

    async def chat(self, **kwargs: str) -> CustomerChatResult:
        self.calls.append(kwargs)
        return CustomerChatResult(
            answer="你正在办理A公司授信。",
            mode="CHAT",
            skill=None,
            committed=True,
            diagnostics=CustomerDiagnostics(
                component_session_id="cs-customer",
                components=("SHORT_TERM_MEMORY", "PLANNING_REASONING", "INFERENCE_ENGINE"),
                context_message_count=2,
                provider="deepseek-direct",
                model="deepseek-chat",
                input_tokens=20,
                output_tokens=10,
                request_id="req-model",
            ),
        )


def test_customer_chat_is_a_natural_language_interface_and_keeps_secrets_server_side(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "core-component-demo-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    fake = FakeCustomerAgent([])
    application = create_app()
    application.dependency_overrides[get_customer_agent] = lambda: fake

    with TestClient(application) as client:
        page = client.get("/")
        response = client.post(
            "/api/customer/chat",
            headers={"Authorization": "Bearer user-token-a"},
            json={"taskId": "task-a", "sessionId": "session-a", "message": "我在办理什么业务？"},
        )

    assert page.status_code == 200
    assert "核心组件智能体" in page.text
    assert response.status_code == 200
    assert response.json()["data"]["answer"] == "你正在办理A公司授信。"
    assert response.json()["data"]["diagnostics"]["components"] == [
        "SHORT_TERM_MEMORY", "PLANNING_REASONING", "INFERENCE_ENGINE"
    ]
    assert fake.calls[0]["message"] == "我在办理什么业务？"
    assert "server-only-secret" not in response.text
