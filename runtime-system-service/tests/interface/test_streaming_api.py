from fastapi.testclient import TestClient

from runtime_system.app import create_app
from runtime_system.identity import StaticTokenIdentityVerifier


def test_streaming_inference_emits_ordered_sse_lifecycle() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"stream-token": {"component:inference-engine:infer"}}
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/inference:stream",
            headers={
                "Authorization": "Bearer stream-token",
                "X-Request-Id": "req-stream-001",
            },
            json={
                "capability": "CHAT",
                "modelAlias": "chat-default",
                "messages": [{"role": "user", "content": "你好"}],
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: response.started" in response.text
    assert "event: response.delta" in response.text
    assert "event: response.usage" in response.text
    assert "event: response.completed" in response.text
    assert response.text.index('"sequence":1') < response.text.index('"sequence":2')
