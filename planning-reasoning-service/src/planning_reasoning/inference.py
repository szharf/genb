from __future__ import annotations

import json
from typing import Literal

import httpx

from .models import SkillGenerateRequest, SkillReviseRequest, ValidationIssue


class ModelAuthoringError(RuntimeError):
    pass


class RuntimeInferenceSkillDraftWriter:
    """Generate complete Skill documents through Runtime System's stable Interface."""

    def __init__(self, *, client: httpx.Client, model_alias: str) -> None:
        self._client = client
        self._model_alias = model_alias

    def generate(
        self,
        *,
        name: str,
        request: SkillGenerateRequest,
        complexity: Literal["SIMPLE", "COMPLEX"],
        service_token: str,
        request_id: str,
    ) -> str:
        system = (
            "你是银行智能体Skill设计专家。只输出完整Skill Markdown，不输出解释、代码围栏或原始思维链。"
            "文档必须包含YAML frontmatter（name和description），以及Purpose、Required Inputs、Workflow、"
            "Constraints、Completion Criteria、Exception Handling章节。复杂Skill还必须包含MCP Tools、"
            "Human Approval和Failure Escalation章节。只声明已提供的工具，不执行任何工具。"
        )
        user = (
            f"Skill技术名称：{name}\n复杂度：{complexity}\n"
            f"已确认需求JSON：\n{request.model_dump_json(by_alias=True)}"
        )
        return self._complete(
            system=system,
            user=user,
            service_token=service_token,
            request_id=request_id,
        )

    def revise(
        self,
        *,
        base_markdown: str,
        request: SkillReviseRequest,
        service_token: str,
        request_id: str,
    ) -> str:
        system = (
            "你是银行智能体Skill修订专家。根据失败摘要修订完整Skill。只输出修订后的完整Markdown，"
            "不要输出差异、解释、代码围栏或原始思维链；不得删除原有安全、人工确认和异常规则。"
        )
        user = (
            f"原Skill：\n{base_markdown}\n\n"
            f"修订请求JSON：\n{request.model_dump_json(by_alias=True)}"
        )
        return self._complete(
            system=system,
            user=user,
            service_token=service_token,
            request_id=request_id,
        )

    def repair(
        self,
        *,
        invalid_markdown: str,
        issues: list[ValidationIssue],
        service_token: str,
        request_id: str,
    ) -> str:
        system = (
            "你是银行智能体Skill格式修复器。根据校验问题修复给定Skill，并保留原有业务语义。"
            "只输出修复后的完整Markdown，不输出解释、代码围栏或原始思维链。"
        )
        user = (
            "校验问题JSON：\n"
            f"{json.dumps([issue.model_dump() for issue in issues], ensure_ascii=False)}\n\n"
            f"待修复Skill：\n{invalid_markdown}"
        )
        return self._complete(
            system=system,
            user=user,
            service_token=service_token,
            request_id=request_id,
        )

    def _complete(
        self,
        *,
        system: str,
        user: str,
        service_token: str,
        request_id: str,
    ) -> str:
        if not service_token:
            raise ModelAuthoringError("MODEL_SERVICE_CREDENTIAL_MISSING")
        try:
            response = self._client.post(
                "/api/v1/runtime-system/inference",
                headers={
                    "Authorization": f"Bearer {service_token}",
                    "X-Request-Id": request_id,
                },
                json={
                    "capability": "SKILL_AUTHORING",
                    "modelAlias": self._model_alias,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            if response.status_code != 200 or len(response.content) > 524_288:
                raise ModelAuthoringError("MODEL_AUTHORING_UNAVAILABLE")
            payload = response.json()
            content = payload["data"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ModelAuthoringError("MODEL_AUTHORING_EMPTY")
            return _strip_markdown_fence(content)
        except ModelAuthoringError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ModelAuthoringError("MODEL_AUTHORING_BAD_RESPONSE") from error


def _strip_markdown_fence(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped
    first_newline = stripped.find("\n")
    if first_newline == -1 or not stripped.endswith("```"):
        return stripped
    return stripped[first_newline + 1 : -3].strip()
