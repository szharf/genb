import time

import httpx


base_url = "http://127.0.0.1:18712/api/v1/planning-reasoning"
suffix = str(int(time.time()))
headers = {
    "X-Tenant-Id": f"http-acceptance-tenant-{suffix}",
    "X-Agent-Id": f"http-acceptance-agent-{suffix}",
    "X-User-Id": "http-acceptance-user",
}
request = {
    "name": "对公授信审查",
    "description": "跨系统检查企业信息、风险信号并形成人工审批建议",
    "requirements": {
        "goal": "完成多步骤对公授信初审",
        "expectedInputs": ["企业统一社会信用代码", "授信申请"],
        "expectedOutputs": ["审查结论", "证据引用", "待人工确认项"],
        "constraints": ["高风险结论必须人工确认", "工具失败不得静默跳过"],
        "riskLevel": "HIGH",
        "toolReferences": [
            {
                "protocol": "MCP",
                "server": "enterprise-registry",
                "tool": "query-company",
                "purpose": "查询企业登记信息",
            }
        ],
    },
}

with httpx.Client(timeout=10) as client:
    clarification = client.post(
        f"{base_url}/requirements:analyze",
        headers=headers,
        json={"goal": "生成授信Skill"},
    )
    clarification.raise_for_status()
    generated_response = client.post(
        f"{base_url}/skills:generate",
        headers={**headers, "Idempotency-Key": f"http-generate-{suffix}"},
        json=request,
    )
    generated_response.raise_for_status()
    generated = generated_response.json()["data"]
    validation = client.post(
        f"{base_url}/skills:validate",
        headers=headers,
        json={"skillMarkdown": generated["skillMarkdown"], "requireMcp": True},
    )
    validation.raise_for_status()
    revised_response = client.post(
        f"{base_url}/skills/{generated['skillId']}:revise",
        headers={**headers, "Idempotency-Key": f"http-revise-{suffix}"},
        json={
            "baseVersion": 1,
            "failure": {
                "failedStep": "企业登记查询",
                "errorCode": "MCP_TIMEOUT",
                "summary": "登记服务超时",
            },
            "adjustmentGoal": "增加人工材料核验降级路径",
        },
    )
    revised_response.raise_for_status()
    revised = revised_response.json()["data"]
    original = client.get(
        f"{base_url}/skills/{generated['skillId']}/versions/1", headers=headers
    )
    original.raise_for_status()

assert clarification.json()["data"]["status"] == "NEEDS_CLARIFICATION"
assert generated["complexity"] == "COMPLEX" and generated["version"] == 1
assert validation.json()["data"]["valid"] is True
assert revised["version"] == 2 and "MCP_TIMEOUT" in revised["skillMarkdown"]
assert "## Revision Context" not in original.json()["data"]["skillMarkdown"]

print(
    {
        "clarification": True,
        "complexSkill": True,
        "mcpDeclaration": "enterprise-registry.query-company" in generated["skillMarkdown"],
        "validation": True,
        "revisionVersion": revised["version"],
        "originalImmutable": True,
    }
)
