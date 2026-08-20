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


def test_local_fake_provider_supports_explicit_session_summary() -> None:
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
                "X-Request-Id": "req-summary-local",
            },
            json={
                "capability": "SESSION_SUMMARY",
                "modelAlias": "session-summary-default",
                "messages": [{"role": "user", "content": "visible conversation"}],
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["content"].startswith("Local-test summary")
    assert response.json()["data"]["provider"] == "FAKE"


def test_local_fake_provider_supports_customer_agent_and_planning_acceptance() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"test-service-token": {"component:inference-engine:infer"}}
        )
    )
    headers = {
        "Authorization": "Bearer test-service-token",
        "X-Request-Id": "req-m5-fake",
    }
    with TestClient(app) as client:
        chat = client.post("/api/v1/runtime-system/inference", headers=headers, json={
            "capability": "AGENT_CHAT", "modelAlias": "agent-chat-default",
            "messages": [{"role": "user", "content": "帮我生成材料检查Skill"}],
        })
        analysis = client.post("/api/v1/runtime-system/inference", headers=headers, json={
            "capability": "SKILL_REQUIREMENT_ANALYSIS", "modelAlias": "planning-analysis-default",
            "messages": [{"role": "user", "content": '{"previousDraft":null,"currentMessage":"生成材料检查Skill"}'}],
        })
        skill = client.post("/api/v1/runtime-system/inference", headers=headers, json={
            "capability": "SKILL_AUTHORING", "modelAlias": "planning-authoring-default",
            "messages": [{"role": "user", "content": "Skill技术名称：material-check\n复杂度：SIMPLE"}],
        })
    assert chat.status_code == 200
    assert '"intent": "CREATE_SKILL"' in chat.json()["data"]["content"]
    assert analysis.status_code == 200
    assert '"status": "CLARIFYING"' in analysis.json()["data"]["content"]
    assert skill.status_code == 200
    assert skill.json()["data"]["content"].startswith("---\nname: material-check")


def test_local_fake_provider_extracts_one_durable_memory_for_real_service_acceptance() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"test-service-token": {"component:inference-engine:infer"}}
        )
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={"Authorization": "Bearer test-service-token", "X-Request-Id": "req-m5-memory"},
            json={
                "capability": "MEMORY_EXTRACTION", "modelAlias": "memory-extraction-default",
                "messages": [{"role": "user", "content": "USER_MESSAGE:\n我长期偏好Markdown检查表\n\nASSISTANT_FINAL:\n已记录"}],
                "responseFormat": {
                    "type": "JSON_SCHEMA", "schemaName": "long_term_memory_extraction_v1",
                    "jsonSchema": {
                        "type": "object", "required": ["memories"], "additionalProperties": False,
                        "properties": {"memories": {"type": "array", "items": {
                            "type": "object", "required": ["type", "content", "confidence", "action"],
                            "additionalProperties": False, "properties": {
                                "type": {"type": "string"}, "content": {"type": "string"},
                                "confidence": {"type": "number"}, "action": {"type": "string"},
                            },
                        }}},
                    },
                },
            },
        )
    assert response.status_code == 200
    assert response.json()["data"]["structured"]["memories"][0]["content"] == "我长期偏好Markdown检查表"
