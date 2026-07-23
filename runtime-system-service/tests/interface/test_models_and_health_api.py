from fastapi.testclient import TestClient

from runtime_system.app import create_app
from runtime_system.identity import StaticTokenIdentityVerifier


def test_models_only_returns_safe_logical_capabilities() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"models-token": {"component:inference-engine:models:read"}}
        )
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/runtime-system/models",
            headers={
                "Authorization": "Bearer models-token",
                "X-Request-Id": "req-models-001",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert [item["modelAlias"] for item in body["data"]] == [
        "chat-default",
        "embedding-default",
        "memory-extraction-default",
    ]
    serialized = response.text.lower()
    assert "secret" not in serialized
    assert "api_key" not in serialized
    assert "endpoint" not in serialized


def test_liveness_does_not_require_model_or_identity() -> None:
    app = create_app(identity_verifier=StaticTokenIdentityVerifier(tokens={}))

    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


def test_local_readiness_reports_fake_provider_explicitly() -> None:
    app = create_app(identity_verifier=StaticTokenIdentityVerifier(tokens={}))

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "UP",
        "environment": "local",
        "providers": [{"provider": "FAKE", "status": "UP"}],
    }


def test_production_cannot_be_ready_with_fake_provider() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(tokens={}),
        environment="production",
    )

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "DOWN"
    assert response.json()["reason"] == "FAKE_PROVIDER_NOT_ALLOWED"


def test_internal_model_health_requires_scope_and_reports_provider() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={
                "health-token": {"component:inference-engine:health:read"}
            }
        )
    )

    with TestClient(app) as client:
        response = client.get(
            "/internal/health/models",
            headers={
                "Authorization": "Bearer health-token",
                "X-Request-Id": "req-health-001",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "data": [{"provider": "FAKE", "status": "UP"}],
        "meta": {"requestId": "req-health-001", "degraded": False},
    }
