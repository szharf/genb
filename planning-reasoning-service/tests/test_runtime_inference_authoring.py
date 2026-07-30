import json

import httpx

from planning_reasoning.inference import RuntimeInferenceSkillDraftWriter
from planning_reasoning.models import FailureEvent, RequirementRequest, SkillGenerateRequest, SkillReviseRequest


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
