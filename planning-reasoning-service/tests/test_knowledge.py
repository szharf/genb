from planning_reasoning.knowledge import ApprovedPlanningKnowledge
from planning_reasoning.models import RequirementDraft


def test_complex_credit_requirement_retrieves_only_approved_references() -> None:
    knowledge = ApprovedPlanningKnowledge()

    references = knowledge.search(
        draft=RequirementDraft(
            goal="检查对公授信材料并调用企业信息查询MCP",
            expectedInputs=["授信申请表"],
            riskLevel="MEDIUM",
        ),
        message="需要生成一个能调用MCP的复杂Skill",
    )

    assert any(item["id"] == "skill-template-credit-document-check" for item in references)
    assert any(item["type"] == "DEVELOPMENT_STANDARD" for item in references)
    assert all(item["authorized"] is True for item in references)
    assert len(references) <= 5
