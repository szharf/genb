from fastapi.testclient import TestClient

from control_system.app import create_app
from control_system.identity import StaticIdentityVerifier
from control_system.protection import HttpProtectionSettings
from control_system.short_term_memory.store import InMemorySessionStore


def _app(settings: HttpProtectionSettings):
    return create_app(
        identity_verifier=StaticIdentityVerifier(credentials={}),
        session_store=InMemorySessionStore(),
        protection_settings=settings,
    )


def test_oversized_control_request_is_rejected_without_echoing_body() -> None:
    app = _app(
        HttpProtectionSettings(
            max_body_bytes=32,
            requests_per_window=10,
            window_seconds=60,
            max_concurrent_requests=2,
            acquire_timeout_seconds=0.05,
        )
    )
    secret = "password=must-not-be-echoed"
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control-system/short-term-memory/turns:commit",
            headers={"X-Request-Id": "req-large"},
            content=secret * 10,
        )

    assert response.status_code == 413
    assert response.json()["code"] == "CONTROL_REQUEST_TOO_LARGE"
    assert secret not in response.text


def test_control_rate_limit_has_retry_hint_and_low_cardinality_metric() -> None:
    app = _app(
        HttpProtectionSettings(
            max_body_bytes=1024,
            requests_per_window=1,
            window_seconds=30,
            max_concurrent_requests=2,
            acquire_timeout_seconds=0.05,
        )
    )
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers={"X-Request-Id": "req-first"},
            json={"query": "hello", "maxContextTokens": 10},
        )
        limited = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers={"X-Request-Id": "req-second"},
            json={"query": "hello", "maxContextTokens": 10},
        )
        metrics = client.get("/metrics")

    assert first.status_code in {401, 403}
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "30"
    assert limited.json()["code"] == "CONTROL_RATE_LIMITED"
    assert 'control_protection_rejections_total{reason="rate_limit"} 1' in metrics.text


def test_health_and_metrics_do_not_consume_business_rate_budget() -> None:
    app = _app(
        HttpProtectionSettings(
            max_body_bytes=1024,
            requests_per_window=1,
            window_seconds=30,
            max_concurrent_requests=1,
            acquire_timeout_seconds=0.05,
        )
    )
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        assert client.get("/metrics").status_code == 200
        business = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers={"X-Request-Id": "req-business"},
            json={"query": "hello", "maxContextTokens": 10},
        )

    assert business.status_code in {401, 403}


def test_metrics_can_be_protected_with_a_dedicated_bearer_secret() -> None:
    app = create_app(
        identity_verifier=StaticIdentityVerifier(credentials={}),
        session_store=InMemorySessionStore(),
        metrics_token="metrics-secret-long-enough",
    )
    with TestClient(app) as client:
        missing = client.get("/metrics")
        wrong = client.get(
            "/metrics", headers={"Authorization": "Bearer wrong-secret-long-enough"}
        )
        accepted = client.get(
            "/metrics",
            headers={"Authorization": "Bearer metrics-secret-long-enough"},
        )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert accepted.status_code == 200
    assert "metrics-secret-long-enough" not in accepted.text
