from fastapi.testclient import TestClient

import short_term_memory.main as main_module
from short_term_memory.identity import InvocationIdentity


class RecordingVerifier:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def verify(
        self,
        *,
        service_token: str,
        actor_token: str,
        required_component: str,
        required_scope: str,
        request_id: str,
    ) -> InvocationIdentity:
        self.calls.append({
            "service_token": service_token,
            "actor_token": actor_token,
            "required_component": required_component,
            "required_scope": required_scope,
            "request_id": request_id,
        })
        if actor_token != "signed-admin-token":
            raise PermissionError("invalid actor token")
        return InvocationIdentity(
            tenant_id="tenant-secure",
            agent_id="genb-component-test",
            user_id="admin-7",
            session_id="direct-session",
            token_type="COMPONENT_ADMIN_TEST",
        )


def test_formal_identity_rejects_self_asserted_headers_without_actor_token(monkeypatch) -> None:
    verifier = RecordingVerifier()
    monkeypatch.setattr(main_module, "identity_verifier", verifier)
    with TestClient(main_module.app) as client:
        response = client.post(
            "/api/v1/short-term-memory/context:prepare",
            headers={
                "X-Tenant-Id": "forged-tenant",
                "X-Agent-Id": "forged-agent",
                "X-User-Id": "forged-user",
            },
            json={"taskId": "secure-task", "sessionId": "secure-session"},
        )

    assert response.status_code == 401


def test_admin_service_test_uses_verified_identity_without_service_credential(monkeypatch) -> None:
    verifier = RecordingVerifier()
    monkeypatch.setattr(main_module, "identity_verifier", verifier)
    with TestClient(main_module.app) as client:
        response = client.post(
            "/api/v1/short-term-memory/context:prepare",
            headers={
                "X-GenB-Actor-Token": "signed-admin-token",
                "X-Request-Id": "req-direct-1",
            },
            json={"taskId": "secure-task", "sessionId": "secure-session"},
        )

    assert response.status_code == 200
    assert verifier.calls == [{
        "service_token": "",
        "actor_token": "signed-admin-token",
        "required_component": "SHORT_TERM_MEMORY",
        "required_scope": "component:short-term-memory:read",
        "request_id": "req-direct-1",
    }]
