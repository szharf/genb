from dataclasses import dataclass

from fastapi.testclient import TestClient

from control_system_test_agent.models import ChatResult
from control_system_test_agent.web import create_app, get_agent


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
