import pytest

from control_system_test_agent.settings import Settings, WebSettings


def test_settings_require_explicit_logical_identity_and_secrets() -> None:
    with pytest.raises(ValueError):
        Settings.from_mapping({})

    settings = Settings.from_mapping(
        {
            "AGENT_ID": "memory-test-a",
            "GENB_BASE_URL": "http://127.0.0.1:8581/api",
            "CONTROL_SYSTEM_BASE_URL": "http://127.0.0.1:8701",
            "SERVICE_CREDENTIAL": "credential-a",
            "USER_TOKEN": "user-token-a",
            "HTTP_TIMEOUT_SECONDS": "3.5",
        }
    )
    assert settings.agent_id == "memory-test-a"
    assert settings.http_timeout_seconds == 3.5


def test_settings_reject_unsupported_urls_and_placeholder_secrets() -> None:
    base = {
        "AGENT_ID": "memory-test-a",
        "GENB_BASE_URL": "file:///tmp/genb",
        "CONTROL_SYSTEM_BASE_URL": "http://127.0.0.1:8701",
        "SERVICE_CREDENTIAL": "${TEST_AGENT_A_CREDENTIAL}",
        "USER_TOKEN": "${TEST_USER_TOKEN}",
    }
    with pytest.raises(ValueError):
        Settings.from_mapping(base)


def test_web_settings_take_user_token_from_each_request() -> None:
    settings = WebSettings.from_mapping({
        "AGENT_ID": "standalone-memory-test-agent",
        "GENB_BASE_URL": "http://127.0.0.1:8581/api",
        "SERVICE_CREDENTIAL": "credential-a",
    })
    assert settings.agent_id == "standalone-memory-test-agent"
    assert not hasattr(settings, "user_token")
