from pathlib import Path

import pytest

from control_system_test_agent.settings import Settings, WebSettings


def test_local_restart_script_uses_supported_http_timeout() -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "restart_customer_core_agent_service_local.ps1"
    )
    script = script_path.read_text(encoding="utf-8")

    assert "$env:HTTP_TIMEOUT_SECONDS = '90'" in script


def test_local_restart_script_requires_redis_and_sso_configuration() -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "restart_customer_core_agent_service_local.ps1"
    )
    script = script_path.read_text(encoding="utf-8")

    assert "[Parameter(Mandatory = $true)][string]$RedisPassword" in script
    assert "$env:AGENT_REDIS_PASSWORD = $RedisPassword" in script
    assert "$env:AGENT_CALLBACK_URL = 'http://localhost:18714/auth/callback'" in script
    assert "$env:PORTAL_AGENT_SSO_URL = 'http://localhost:9100/agent-sso'" in script


def test_full_local_start_configures_agent_redis_and_sso_public_urls() -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "start_customer_core_agent_local.ps1"
    )
    script = script_path.read_text(encoding="utf-8")

    assert "$env:AGENT_REDIS_HOST = '127.0.0.1'" in script
    assert "$env:AGENT_REDIS_PORT = '6379'" in script
    assert "$env:AGENT_REDIS_PASSWORD = $RedisPassword" in script
    assert "$env:AGENT_CALLBACK_URL = 'http://localhost:18714/auth/callback'" in script
    assert "$env:PORTAL_AGENT_SSO_URL = 'http://localhost:9100/agent-sso'" in script
    assert "callbackUrl = 'http://localhost:18714/auth/callback'" in script
    assert "gateway=http://localhost:9100/core-agent/" not in script
    assert "direct=http://127.0.0.1:18714/" in script


def test_full_local_start_keeps_planning_tables_in_genb_schema() -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "start_customer_core_agent_local.ps1"
    )
    script = script_path.read_text(encoding="utf-8")

    assert (
        '$env:PLANNING_REASONING_POSTGRES_DSN = "host=127.0.0.1 port=5432 '
        'dbname=genb_local user=$dbUser password=$dbPassword sslmode=disable '
        "options='-c search_path=bank_agent_db'\""
    ) in script


@pytest.mark.parametrize(
    "script_name",
    [
        "start_planning_reasoning_service.ps1",
        "start_planning_integration_local.ps1",
        "start_customer_core_agent_services_only_local.ps1",
    ],
)
def test_other_local_planning_starts_keep_tables_in_genb_schema(script_name: str) -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / script_name

    assert "options='-c search_path=bank_agent_db'" in script_path.read_text(encoding="utf-8")


def test_web_settings_allow_model_generation_timeout_but_reject_unbounded_values() -> None:
    base = {
        "AGENT_ID": "core-component-demo-agent",
        "GENB_BASE_URL": "http://127.0.0.1:8581/api",
        "SERVICE_CREDENTIAL": "credential-a",
    }
    assert WebSettings.from_mapping({**base, "HTTP_TIMEOUT_SECONDS": "90"}).http_timeout_seconds == 90
    with pytest.raises(ValueError):
        WebSettings.from_mapping({**base, "HTTP_TIMEOUT_SECONDS": "121"})


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
