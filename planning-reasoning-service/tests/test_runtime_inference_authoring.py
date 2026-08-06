import json

import httpx

from planning_reasoning.inference import (
    RuntimeInferenceRequirementAnalyst,
    RuntimeInferenceSkillDraftWriter,
)
from planning_reasoning.models import (
    FailureEvent,
    RequirementDraft,
    RequirementRequest,
    SkillGenerateRequest,
    SkillReviseRequest,
)


VALID_SKILL = """---
name: credit-review
description: 模型生成的授信审查Skill
---

# 授信审查

## Purpose

完成授信审查。

## Required Inputs

- 授信申请

## Workflow

1. 检查输入。

## Constraints

- 不得修改原始材料。

## Completion Criteria

- 输出审查结论。

## Exception Handling

- 输入缺失时暂停。
"""


def _request() -> SkillGenerateRequest:
    return SkillGenerateRequest(
        name="授信审查",
        description="检查授信材料并生成经过复核的审查结论",
        requirements=RequirementRequest(
            goal="完成授信审查",
            expectedInputs=["授信申请"],
            expectedOutputs=["审查结论"],
            constraints=["不得修改原始材料"],
        ),
    )


def test_model_writer_calls_runtime_with_logical_alias_and_returns_skill() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["request_id"] = request.headers["X-Request-Id"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "data": {
                    "content": VALID_SKILL,
                    "structured": None,
                    "modelAlias": "planning-authoring-default",
                    "model": "approved-model",
                    "provider": "direct-provider",
                    "usage": {"inputTokens": 20, "outputTokens": 30, "totalTokens": 50, "estimated": False},
                    "finishReason": "STOP",
                },
                "meta": {
                    "requestId": "req-model",
                    "componentCode": "INFERENCE_ENGINE",
                    "implementationCode": "runtime-inference-default",
                    "interfaceVersion": "1.0.0",
                    "degraded": False,
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://runtime") as client:
        writer = RuntimeInferenceSkillDraftWriter(client=client, model_alias="planning-authoring-default")
        markdown = writer.generate(
            name="credit-review",
            request=_request(),
            complexity="SIMPLE",
            service_token="agent-service-credential",
            request_id="req-model",
        )

    assert markdown == VALID_SKILL.strip()
    assert captured["authorization"] == "Bearer agent-service-credential"
    assert captured["request_id"] == "req-model"
    assert captured["body"]["modelAlias"] == "planning-authoring-default"
    assert captured["body"]["capability"] == "SKILL_AUTHORING"
    assert "原始思维链" in captured["body"]["messages"][0]["content"]


def test_model_writer_revises_the_complete_skill_instead_of_appending_a_stub() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert VALID_SKILL in body["messages"][1]["content"]
        assert "TOOL_TIMEOUT" in body["messages"][1]["content"]
        return httpx.Response(200, json={"data": {"content": VALID_SKILL + "\n- 工具超时最多重试两次。"}})

    revision = SkillReviseRequest(
        baseVersion=1,
        failure=FailureEvent(failedStep="查询企业", errorCode="TOOL_TIMEOUT", summary="查询超时"),
        adjustmentGoal="最多重试两次后转人工",
    )
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://runtime") as client:
        writer = RuntimeInferenceSkillDraftWriter(client=client, model_alias="planning-authoring-default")
        markdown = writer.revise(
            base_markdown=VALID_SKILL,
            request=revision,
            service_token="agent-service-credential",
            request_id="req-revise",
        )

    assert "工具超时最多重试两次" in markdown


def test_model_writer_repairs_invalid_skill_with_validation_issues() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"data": {"content": VALID_SKILL}})

    from planning_reasoning.models import ValidationIssue

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://runtime") as client:
        writer = RuntimeInferenceSkillDraftWriter(client=client, model_alias="planning-authoring-default")
        repaired = writer.repair(
            invalid_markdown="# incomplete",
            issues=[ValidationIssue(code="INVALID_FRONTMATTER", message="frontmatter缺失")],
            service_token="agent-service-credential",
            request_id="req-repair",
        )

    assert repaired == VALID_SKILL.strip()
    assert "INVALID_FRONTMATTER" in captured["body"]["messages"][1]["content"]
    assert captured["body"]["messages"][0]["content"].startswith("你是银行智能体Skill格式修复器")


def test_requirement_analyst_uses_previous_facts_and_returns_dynamic_questions() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "data": {
                    "content": json.dumps(
                        {
                            "status": "CLARIFYING",
                            "complexity": "COMPLEX",
                            "draft": {
                                "name": "授信材料检查",
                                "description": "检查授信材料并生成缺失项清单",
                                "goal": "检查A公司授信材料",
                                "expectedInputs": ["授信申请表"],
                                "expectedOutputs": [],
                                "constraints": ["不得修改原始材料"],
                                "preferredTools": [],
                                "toolReferences": [],
                                "riskLevel": "MEDIUM",
                            },
                            "questions": [
                                {
                                    "questionId": "q-output-format",
                                    "field": "expectedOutputs",
                                    "topic": "OUTPUT",
                                    "question": "希望缺失项清单使用表格还是JSON？",
                                    "reason": "输出格式会影响Skill完成条件。",
                                    "inputHint": "例如：表格，包含材料名称和缺失原因。",
                                    "required": True,
                                }
                            ],
                            "references": [],
                            "decisionSummary": "已保留申请表和禁止修改原件两项需求。",
                        },
                        ensure_ascii=False,
                    )
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://runtime") as client:
        analyst = RuntimeInferenceRequirementAnalyst(
            client=client, model_alias="planning-analysis-default"
        )
        result = analyst.analyze(
            previous=RequirementDraft(
                name="授信材料检查",
                description="检查授信材料并生成缺失项清单",
                goal="检查A公司授信材料",
                expectedInputs=["授信申请表"],
                constraints=["不得修改原始材料"],
                riskLevel="MEDIUM",
            ),
            message="结果给我一个清单就可以",
            references=[
                {
                    "id": "skill-template-credit-review",
                    "type": "SKILL_TEMPLATE",
                    "name": "授信材料检查模板",
                    "summary": "逐项检查授信材料完整性",
                    "source": "GENB_APPROVED",
                    "authorized": True,
                }
            ],
            service_token="agent-service-credential",
            request_id="req-analysis",
        )

    system_prompt = captured["body"]["messages"][0]["content"]
    user_prompt = captured["body"]["messages"][1]["content"]
    assert "已经回答过的问题不得重复" in system_prompt
    assert "每轮最多询问3个" in system_prompt
    assert "授信申请表" in user_prompt
    assert "skill-template-credit-review" in user_prompt
    assert result.questions[0].question == "希望缺失项清单使用表格还是JSON？"
    assert result.draft.expected_inputs == ["授信申请表"]


def test_requirement_analyst_normalizes_common_structured_model_variations() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"content": json.dumps({
            "status": "CLARIFYING",
            "complexity": "COMPLEX",
            "draft": {
                "name": "银行对公授信材料检查Skill",
                "description": "用于银行对公授信申请材料的完整性检查",
                "goal": "检查对公授信材料",
                "expectedInputs": [],
                "expectedOutputs": [{"name": "检查报告", "description": "结构化报告"}],
                "constraints": [],
                "preferredTools": [],
                "toolReferences": [{
                    "id": "skill-template-credit-review", "type": "SKILL_TEMPLATE",
                    "source": "GENB_APPROVED", "authorized": True,
                }],
                "riskLevel": "高风险",
                "confirmedFacts": [{
                    "field": "人工审批规则", "value": "高风险需人工确认",
                    "source": "POLICY", "confirmed": False,
                }],
                "candidateFacts": [{
                    "field": "业务领域", "value": "银行对公授信",
                    "source": "USER", "confirmed": True,
                }],
                "unknownFields": ["输入形式"], "conflicts": [],
                "askedQuestionIds": [], "askedQuestions": [],
            },
            "questions": [{
                "questionId": "q-input", "field": "inputFormat", "topic": "INPUT",
                "question": "材料将以什么形式输入？", "reason": "决定解析方式",
                "inputHint": "例如PDF", "required": True,
            }],
            "references": {"approvedReferences": []},
            "decisionSummary": "需要确认输入形式。",
        }, ensure_ascii=False)}})

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://runtime") as client:
        result = RuntimeInferenceRequirementAnalyst(
            client=client, model_alias="planning-analysis-default"
        ).analyze(
            previous=None, message="生成授信材料检查Skill", references=[],
            service_token="agent-service-credential", request_id="req-normalize",
        )

    assert result.draft.risk_level == "HIGH"
    assert result.draft.expected_outputs == ["检查报告：结构化报告"]
    assert result.references == []
    assert result.draft.confirmed_facts[0]["field"] == "业务领域"
    assert result.draft.candidate_facts[0]["field"] == "人工审批规则"
    assert result.draft.tool_references == []


def test_requirement_analyst_clarifies_unknown_risk_instead_of_returning_bad_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"content": json.dumps({
            "status": "READY",
            "complexity": "COMPLEX",
            "draft": {
                "name": "授信材料检查",
                "description": "检查银行对公授信申请材料并输出完整性结果",
                "goal": "检查对公授信材料",
                "expectedInputs": ["授信申请", "企业材料"],
                "expectedOutputs": ["缺失材料清单", "人工复核建议"],
                "constraints": ["高风险结论必须人工确认"],
                "preferredTools": [],
                "toolReferences": [],
                "riskLevel": "UNKNOWN",
                "confirmedFacts": [],
                "candidateFacts": [],
                "unknownFields": [],
                "conflicts": [],
                "askedQuestionIds": [],
                "askedQuestions": [],
            },
            "questions": [],
            "references": [],
            "decisionSummary": "需求已经完整。",
        }, ensure_ascii=False)}})

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://runtime") as client:
        result = RuntimeInferenceRequirementAnalyst(
            client=client, model_alias="planning-analysis-default"
        ).analyze(
            previous=None, message="生成授信材料检查Skill", references=[],
            service_token="agent-service-credential", request_id="req-unknown-risk",
        )

    assert result.status == "CLARIFYING"
    assert result.draft.risk_level == "MEDIUM"
    assert "riskLevel" in result.draft.unknown_fields
    assert result.questions[0].question_id == "q-risk-level"
