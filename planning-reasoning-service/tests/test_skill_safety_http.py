from fastapi.testclient import TestClient

from planning_reasoning.main import app


HEADERS = {
    "X-Tenant-Id": "tenant-safety",
    "X-Agent-Id": "agent-safety",
    "X-User-Id": "user-safety",
}

REQUEST = {
    "name": "材料完整性检查",
    "description": "检查业务材料完整性并输出缺失项",
    "requirements": {
        "goal": "检查材料完整性",
        "expectedInputs": ["业务材料"],
        "expectedOutputs": ["缺失项"],
        "constraints": ["不得修改输入"],
    },
}


def test_generation_is_idempotent_and_rejects_conflicting_key_reuse() -> None:
    headers = {**HEADERS, "Idempotency-Key": "safety-generate-001"}
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/planning-reasoning/skills:generate", headers=headers, json=REQUEST
        )
        replay = client.post(
            "/api/v1/planning-reasoning/skills:generate", headers=headers, json=REQUEST
        )
        conflict = client.post(
            "/api/v1/planning-reasoning/skills:generate",
            headers=headers,
            json={**REQUEST, "description": "同一个幂等键不能用于不同生成请求"},
        )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["data"]["skillId"] == first.json()["data"]["skillId"]
    assert conflict.status_code == 409


def test_generation_is_blocked_until_required_clarifications_are_answered() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/planning-reasoning/skills:generate",
            headers={**HEADERS, "Idempotency-Key": "safety-incomplete-001"},
            json={
                "name": "不完整Skill",
                "description": "这个请求缺少必要的输入输出和约束信息",
                "requirements": {"goal": "生成一个Skill"},
            },
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "REQUIREMENT_CLARIFICATION_REQUIRED"
    assert detail["analysis"]["status"] == "NEEDS_CLARIFICATION"


def test_skill_versions_are_isolated_by_verified_tenant_and_agent() -> None:
    with TestClient(app) as client:
        generated = client.post(
            "/api/v1/planning-reasoning/skills:generate",
            headers={**HEADERS, "Idempotency-Key": "safety-isolation-001"},
            json=REQUEST,
        ).json()["data"]
        hidden = client.get(
            f"/api/v1/planning-reasoning/skills/{generated['skillId']}/versions/1",
            headers={**HEADERS, "X-Agent-Id": "another-agent"},
        )

    assert hidden.status_code == 404
