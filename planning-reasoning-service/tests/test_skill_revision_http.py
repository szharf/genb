from fastapi.testclient import TestClient

from planning_reasoning.main import app


HEADERS = {
    "X-Tenant-Id": "tenant-revision",
    "X-Agent-Id": "agent-revision",
    "X-User-Id": "user-a",
}


def test_failure_revision_creates_new_version_without_overwriting_original() -> None:
    with TestClient(app) as client:
        generated = client.post(
            "/api/v1/planning-reasoning/skills:generate",
            headers={**HEADERS, "Idempotency-Key": "revision-generate-001"},
            json={
                "name": "对公授信审查",
                "description": "跨系统检查企业信息并形成人工审批建议",
                "requirements": {
                    "goal": "完成多步骤对公授信初审",
                    "expectedInputs": ["授信申请"],
                    "expectedOutputs": ["审批建议"],
                    "constraints": ["高风险结论必须人工确认"],
                    "riskLevel": "HIGH",
                },
            },
        ).json()["data"]
        skill_id = generated["skillId"]

        revised_response = client.post(
            f"/api/v1/planning-reasoning/skills/{skill_id}:revise",
            headers={**HEADERS, "Idempotency-Key": "revision-event-001"},
            json={
                "baseVersion": 1,
                "failure": {
                    "failedStep": "企业信息查询",
                    "errorCode": "MCP_TIMEOUT",
                    "summary": "企业登记服务连续超时",
                },
                "adjustmentGoal": "增加人工材料核对作为降级路径",
            },
        )
        original_response = client.get(
            f"/api/v1/planning-reasoning/skills/{skill_id}/versions/1",
            headers=HEADERS,
        )

    assert revised_response.status_code == 201
    revised = revised_response.json()["data"]
    assert revised["version"] == 2
    assert revised["skillId"] == skill_id
    assert "## Revision Context" in revised["skillMarkdown"]
    assert "MCP_TIMEOUT" in revised["skillMarkdown"]
    assert "增加人工材料核对作为降级路径" in revised["skillMarkdown"]
    assert original_response.status_code == 200
    original = original_response.json()["data"]
    assert original["version"] == 1
    assert "## Revision Context" not in original["skillMarkdown"]
