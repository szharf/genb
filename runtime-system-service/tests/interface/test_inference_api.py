from fastapi.testclient import TestClient

from runtime_system.app import create_app
from runtime_system.identity import StaticTokenIdentityVerifier
from runtime_system.provider import FakeModelProvider


def test_authorized_caller_can_run_inference_through_the_public_interface() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"test-service-token": {"component:inference-engine:infer"}}
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer test-service-token",
                "X-Request-Id": "req-tracer-001",
            },
            json={
                "capability": "CHAT",
                "modelAlias": "chat-default",
                "messages": [{"role": "user", "content": "你好"}],
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "content": "你好",
            "structured": None,
            "modelAlias": "chat-default",
            "model": "fake-chat-v1",
            "provider": "FAKE",
            "usage": {
                "inputTokens": 2,
                "outputTokens": 2,
                "totalTokens": 4,
                "estimated": True,
            },
            "finishReason": "STOP",
        },
        "meta": {
            "requestId": "req-tracer-001",
            "componentCode": "INFERENCE_ENGINE",
            "implementationCode": "runtime-inference-fake",
            "interfaceVersion": "1.0.0",
            "degraded": False,
        },
    }


def test_inference_requires_authentication() -> None:
    app = create_app(identity_verifier=StaticTokenIdentityVerifier(tokens={}))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={"X-Request-Id": "req-no-auth"},
            json={
                "capability": "CHAT",
                "modelAlias": "chat-default",
                "messages": [{"role": "user", "content": "你好"}],
            },
        )

    assert response.status_code == 401
    assert response.json()["code"] == "MODEL_CALLER_UNAUTHENTICATED"
    assert response.json()["requestId"] == "req-no-auth"


def test_inference_requires_the_infer_scope() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"wrong-scope-token": {"component:inference-engine:embed"}}
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer wrong-scope-token",
                "X-Request-Id": "req-wrong-scope",
            },
            json={
                "capability": "CHAT",
                "modelAlias": "chat-default",
                "messages": [{"role": "user", "content": "你好"}],
            },
        )

    assert response.status_code == 403
    assert response.json()["code"] == "MODEL_SCOPE_DENIED"


def test_invalid_inference_request_uses_problem_details_without_echoing_content() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"test-service-token": {"component:inference-engine:infer"}}
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer test-service-token",
                "X-Request-Id": "req-invalid-request",
            },
            json={
                "capability": "CHAT",
                "modelAlias": "chat-default",
                "messages": [],
                "sensitive": "do-not-echo",
            },
        )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "MODEL_REQUEST_INVALID"
    assert response.json()["requestId"] == "req-invalid-request"
    assert "do-not-echo" not in response.text


def test_structured_inference_returns_schema_valid_json() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"test-service-token": {"component:inference-engine:infer"}}
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer test-service-token",
                "X-Request-Id": "req-structured-001",
            },
            json={
                "capability": "MEMORY_EXTRACTION",
                "modelAlias": "memory-extraction-default",
                "messages": [{"role": "user", "content": "用户偏好稳健投资"}],
                "responseFormat": {
                    "type": "JSON_SCHEMA",
                    "schemaName": "memory_extraction_v1",
                    "jsonSchema": {
                        "type": "object",
                        "required": ["memories"],
                        "properties": {"memories": {"type": "array"}},
                        "additionalProperties": False,
                    },
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["structured"] == {"memories": []}


def test_invalid_structured_provider_output_returns_problem_details() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"test-service-token": {"component:inference-engine:infer"}}
        ),
        provider=FakeModelProvider(structured_content="not-json"),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer test-service-token",
                "X-Request-Id": "req-invalid-json",
            },
            json={
                "capability": "MEMORY_EXTRACTION",
                "modelAlias": "memory-extraction-default",
                "messages": [{"role": "user", "content": "用户偏好稳健投资"}],
                "responseFormat": {
                    "type": "JSON_SCHEMA",
                    "schemaName": "memory_extraction_v1",
                    "jsonSchema": {
                        "type": "object",
                        "required": ["memories"],
                        "properties": {"memories": {"type": "array"}},
                        "additionalProperties": False,
                    },
                },
            },
        )

    assert response.status_code == 422
    assert response.json()["code"] == "MODEL_STRUCTURED_OUTPUT_INVALID"
    assert response.json()["requestId"] == "req-invalid-json"
