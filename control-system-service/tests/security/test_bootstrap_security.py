import pytest

from control_system.bootstrap import create_local_app


def test_local_credential_adapter_is_forbidden_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="forbidden outside local/test"):
        create_local_app()
