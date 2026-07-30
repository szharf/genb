from planning_reasoning.models import RequirementRequest, SkillGenerateRequest
from planning_reasoning.repository import InMemorySkillRepository
from planning_reasoning.service import RequirementAnalyzer, SkillAuthoringService, SkillValidator


VALID = """---
name: repaired-skill
description: 已自动修复格式的测试Skill
---

## Purpose
完成测试。
## Required Inputs
- 输入
## Workflow
1. 执行。
## Constraints
- 不得越权。
## Completion Criteria
- 输出
## Exception Handling
- 失败时停止。
"""


class RepairingWriter:
    def __init__(self) -> None:
        self.repair_calls = 0

    def generate(self, **_kwargs) -> str:
        return "# invalid"

    def repair(self, **kwargs) -> str:
        self.repair_calls += 1
        assert kwargs["issues"]
        assert kwargs["request_id"] == "req-generate-repair"
        return VALID

    def revise(self, **_kwargs) -> str:
        raise AssertionError("not used")


def test_generation_repairs_invalid_model_draft_once_before_saving() -> None:
    writer = RepairingWriter()
    service = SkillAuthoringService(
        RequirementAnalyzer(), SkillValidator(), InMemorySkillRepository(), writer
    )
    artifact = service.generate(
        SkillGenerateRequest(
            name="测试Skill",
            description="这是一个用于验证自动修复行为的测试Skill",
            requirements=RequirementRequest(
                goal="验证修复",
                expectedInputs=["输入"],
                expectedOutputs=["输出"],
                constraints=["不得越权"],
            ),
        ),
        tenant_id="tenant-a",
        agent_id="agent-a",
        idempotency_key="repair-once",
        service_token="credential",
        request_id="req-generate",
    )

    assert writer.repair_calls == 1
    assert artifact.validation.valid is True
    assert artifact.skill_markdown == VALID


def test_generation_falls_back_to_safe_template_when_repair_is_still_invalid() -> None:
    class InvalidWriter(RepairingWriter):
        def repair(self, **_kwargs) -> str:
            self.repair_calls += 1
            return "still invalid"

    writer = InvalidWriter()
    service = SkillAuthoringService(
        RequirementAnalyzer(), SkillValidator(), InMemorySkillRepository(), writer
    )
    artifact = service.generate(
        SkillGenerateRequest(
            name="测试Skill",
            description="这是一个用于验证安全模板回退的测试Skill",
            requirements=RequirementRequest(
                goal="验证安全回退",
                expectedInputs=["输入"],
                expectedOutputs=["输出"],
                constraints=["不得越权"],
            ),
        ),
        tenant_id="tenant-a",
        agent_id="agent-a",
        idempotency_key="fallback-template",
        service_token="credential",
        request_id="req-fallback",
    )

    assert writer.repair_calls == 1
    assert artifact.validation.valid is True
    assert "## Workflow" in artifact.skill_markdown
    assert "回退到安全标准模板" in artifact.decision_summary
