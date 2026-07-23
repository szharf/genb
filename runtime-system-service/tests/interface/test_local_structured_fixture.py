import pytest
from fastapi.testclient import TestClient

from runtime_system.main import build_app


def test_local_structured_fixture_supports_memory_acceptance(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("RUNTIME_STATIC_TOKEN", "runtime-acceptance-token")
    monkeypatch.setenv(
        "RUNTIME_FAKE_STRUCTURED_CONTENT",
        '{"memories":[{"type":"USER_PREFERENCE","content":"prefers tea",'
        '"confidence":0.95,"action":"UPSERT"}]}',
    )
    with TestClient(build_app()) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer runtime-acceptance-token",
                "X-Request-Id": "req-memory-acceptance",
            },
            json={
                "capability": "MEMORY_EXTRACTION",
                "modelAlias": "memory-acceptance",
                "messages": [{"role": "user", "content": "I prefer tea"}],
                "responseFormat": {
                    "type": "JSON_SCHEMA",
                    "schemaName": "memory",
                    "jsonSchema": {
                        "type": "object",
                        "required": ["memories"],
                        "properties": {"memories": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["type", "content", "confidence", "action"],
                                "properties": {
                                    "type": {"type": "string"},
                                    "content": {"type": "string"},
                                    "confidence": {"type": "number"},
                                    "action": {"type": "string"},
                                },
                                "additionalProperties": False,
                            },
                        }},
                        "additionalProperties": False,
                    },
                },
            },
        )
    assert response.status_code == 200
    assert response.json()["data"]["structured"]["memories"][0]["type"] == "USER_PREFERENCE"


def test_structured_fixture_is_forbidden_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RUNTIME_FAKE_STRUCTURED_CONTENT", '{"memories":[]}')
    with pytest.raises(RuntimeError, match="forbidden"):
        build_app()
