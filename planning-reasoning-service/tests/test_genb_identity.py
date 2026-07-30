from fastapi.testclient import TestClient

import planning_reasoning.main as main_module
from planning_reasoning.identity import InvocationIdentity


class RecordingVerifier:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def verify(self, **kwargs: str) -> InvocationIdentity:
        self.calls.append(kwargs)
        if kwargs["actor_token"] != "signed-actor-token":
            raise PermissionError("invalid actor token")
        return InvocationIdentity(
            tenant_id="tenant-secure",
            agent_id="agent-secure",
            user_id="user-secure",
            session_id="session-secure",
            token_type="COMPONENT_SESSION",
        )


def test_formal_identity_ignores_forged_identity_headers_and_requires_actor(monkeypatch) -> None:
    verifier = RecordingVerifier()
    monkeypatch.setattr(main_module, "identity_verifier", verifier)
    with TestClient(main_module.app) as client:
        rejected = client.post(
            "/api/v1/planning-reasoning/requirements:analyze",
            headers={
                "X-Tenant-Id": "forged-tenant",
                "X-Agent-Id": "forged-agent",
                "X-User-Id": "forged-user",
            },
            json={"goal": "生成Skill"},
        )
        accepted = client.post(
            "/api/v1/planning-reasoning/requirements:analyze",
            headers={
                "Authorization": "Bearer service-secret",
                "X-GenB-Actor-Token": "signed-actor-token",
                "X-Request-Id": "req-planning-1",
            },
            json={"goal": "生成Skill"},
        )

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert verifier.calls[-1] == {
        "service_token": "service-secret",
        "actor_token": "signed-actor-token",
        "required_component": "PLANNING_REASONING",
        "required_scope": "component:planning-reasoning:invoke",
        "request_id": "req-planning-1",
    }
