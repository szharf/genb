import json

import pytest
from fastapi.testclient import TestClient

from runtime_system.main import build_app


def _routing_document():
    return {
        "schemaVersion": "1.0",
        "providers": [
            {
                "providerId": "local-provider",
                "type": "OPENAI_COMPATIBLE",
                "baseUrl": "https://provider.example/v1",
                "secretRef": "env://LOCAL_PROVIDER_KEY",
                "timeoutMs": 30000,
            }
        ],
        "routes": [
            {
                "routeId": "agent-chat",
                "modelAlias": "agent-chat-default",
                "capabilities": ["CHAT"],
                "providerId": "local-provider",
                "model": "approved-model",
            }
        ],
    }


def test_local_runtime_loads_provider_secret_from_private_env_file(tmp_path, monkeypatch):
    routing_path = tmp_path / "routing.json"
    routing_path.write_text(json.dumps(_routing_document()), encoding="utf-8")
    secret_path = tmp_path / "provider.env"
    secret_path.write_text("# local only\nLOCAL_PROVIDER_KEY=test-secret\n", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("RUNTIME_STATIC_TOKEN", "local-test-token")
    monkeypatch.setenv("MODEL_ROUTING_CONFIG", str(routing_path))
    monkeypatch.setenv("RUNTIME_LOCAL_ENV_FILE", str(secret_path))
    monkeypatch.delenv("LOCAL_PROVIDER_KEY", raising=False)

    with TestClient(build_app()) as client:
        response = client.get(
            "/api/v1/runtime-system/models",
            headers={
                "Authorization": "Bearer local-test-token",
                "X-Request-Id": "req-local-secret",
            },
        )

    assert response.status_code == 200
    assert response.json()["data"][0]["modelAlias"] == "agent-chat-default"
    assert "test-secret" not in response.text


def test_production_runtime_rejects_local_secret_env_file(tmp_path, monkeypatch):
    secret_path = tmp_path / "provider.env"
    secret_path.write_text("LOCAL_PROVIDER_KEY=test-secret\n", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RUNTIME_LOCAL_ENV_FILE", str(secret_path))

    with pytest.raises(RuntimeError, match="RUNTIME_LOCAL_ENV_FILE is forbidden"):
        build_app()
