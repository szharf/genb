from fastapi.testclient import TestClient

from planning_reasoning.main import app


HEADERS = {
    "X-Tenant-Id": "tenant-a",
    "X-Agent-Id": "agent-a",
    "X-User-Id": "user-a",
}


def test_incomplete_request_returns_questions_before_skill_generation() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/planning-reasoning/requirements:analyze",
            headers=HEADERS,
            json={"goal": "生成一个授信审查Skill"},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "NEEDS_CLARIFICATION"
    assert data["complexity"] == "SIMPLE"
    assert {question["field"] for question in data["questions"]} == {
        "expectedInputs",
        "expectedOutputs",
        "constraints",
    }
    assert all(question["question"].strip() for question in data["questions"])


def test_a_single_declared_mcp_tool_selects_the_complex_template() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/planning-reasoning/requirements:analyze",
            headers=HEADERS,
            json={
                "goal": "查询企业登记信息后输出摘要",
                "expectedInputs": ["统一社会信用代码"],
                "expectedOutputs": ["企业信息摘要"],
                "constraints": ["保留数据来源"],
                "toolReferences": [
                    {
                        "protocol": "MCP",
                        "server": "enterprise-registry",
                        "tool": "query-company",
                        "purpose": "查询企业登记信息",
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["complexity"] == "COMPLEX"
