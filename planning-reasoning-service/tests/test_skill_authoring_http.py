from fastapi.testclient import TestClient

from planning_reasoning.service import _skill_name

from planning_reasoning.main import app


HEADERS = {
    "X-Tenant-Id": "tenant-a",
    "X-Agent-Id": "agent-a",
    "X-User-Id": "user-a",
}


def test_simple_requirement_generates_a_valid_versioned_skill() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/planning-reasoning/skills:generate",
            headers={**HEADERS, "Idempotency-Key": "skill-simple-001"},
            json={
                "name": "授信材料检查",
                "description": "检查申请材料是否齐全并输出缺失清单",
                "requirements": {
                    "goal": "检查授信申请材料",
                    "expectedInputs": ["授信申请表", "材料清单"],
                    "expectedOutputs": ["缺失材料清单"],
                    "constraints": ["不得修改原始材料"],
                },
            },
        )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["complexity"] == "SIMPLE"
    assert data["version"] == 1
    assert data["skillId"].startswith("skill_")
    assert data["skillMarkdown"].startswith("---\nname: credit-material-check")
    assert "## Workflow" in data["skillMarkdown"]
    assert "## Completion Criteria" in data["skillMarkdown"]
    assert "MCP" not in data["skillMarkdown"]
    assert data["validation"]["valid"] is True
    assert "chainOfThought" not in response.text


def test_complex_requirement_uses_mcp_and_human_approval_template() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/planning-reasoning/skills:generate",
            headers={**HEADERS, "Idempotency-Key": "skill-complex-001"},
            json={
                "name": "对公授信审查",
                "description": "跨系统检查企业信息、风险信号并形成人工审批建议",
                "requirements": {
                    "goal": "完成多步骤对公授信初审",
                    "expectedInputs": ["企业统一社会信用代码", "授信申请"],
                    "expectedOutputs": ["审查结论", "证据引用", "待人工确认项"],
                    "constraints": ["高风险结论必须人工确认", "任何工具失败不得静默跳过"],
                    "riskLevel": "HIGH",
                    "toolReferences": [
                        {
                            "protocol": "MCP",
                            "server": "enterprise-registry",
                            "tool": "query-company",
                            "purpose": "查询企业登记信息",
                        },
                        {
                            "protocol": "MCP",
                            "server": "risk-engine",
                            "tool": "evaluate-credit-risk",
                            "purpose": "评估信用风险",
                        },
                    ],
                },
            },
        )

    assert response.status_code == 201
    data = response.json()["data"]
    markdown = data["skillMarkdown"]
    assert data["complexity"] == "COMPLEX"
    assert "## MCP Tools" in markdown
    assert "enterprise-registry.query-company" in markdown
    assert "risk-engine.evaluate-credit-risk" in markdown
    assert "## Human Approval" in markdown
    assert "## Failure Escalation" in markdown
    assert data["validation"]["valid"] is True
def test_chinese_display_name_with_generic_skill_suffix_gets_meaningful_technical_name() -> None:
    assert _skill_name("银行对公授信材料检查Skill") == "corporate-credit-material-check"
