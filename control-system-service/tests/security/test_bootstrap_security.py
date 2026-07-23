import pytest
from fastapi.testclient import TestClient

from control_system.bootstrap import create_genb_connected_app, create_local_app


def test_local_credential_adapter_is_forbidden_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="forbidden outside local/test"):
        create_local_app()


def test_production_genb_adapter_requires_https(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.internal")
    monkeypatch.setenv("CONTROL_SYSTEM_INTERNAL_TOKEN", "internal-token-production")
    monkeypatch.setenv("REDIS_KEY_PEPPER", "production-key-pepper")

    with pytest.raises(RuntimeError, match="HTTPS"):
        create_genb_connected_app()


def test_genb_adapter_can_bootstrap_without_local_credential_files(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.internal")
    monkeypatch.setenv("CONTROL_SYSTEM_INTERNAL_TOKEN", "internal-token-for-test")
    monkeypatch.setenv("REDIS_KEY_PEPPER", "test-key-pepper-value")
    monkeypatch.delenv("CONTROL_SYSTEM_ACTOR_PUBLIC_KEY_PATH", raising=False)
    monkeypatch.delenv("CONTROL_SYSTEM_LOCAL_CREDENTIALS_PATH", raising=False)

    app = create_genb_connected_app()

    with TestClient(app):
        assert app.title == "GenB Control System"
