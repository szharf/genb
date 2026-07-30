import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import uuid4

from .models import (
    ClarificationQuestion,
    RequirementAnalysis,
    RequirementRequest,
    SkillArtifact,
    SkillGenerateRequest,
    SkillReviseRequest,
    SkillValidation,
    ValidationIssue,
)
from .repository import SkillRepository


QUESTION_TEXT = {
    "expectedInputs": "执行这个Skill前必须由谁提供哪些输入或材料？",
    "expectedOutputs": "Skill完成后必须交付哪些结果，采用什么格式？",
    "constraints": "执行过程中有哪些业务规则、禁止事项或审批约束？",
}


class SkillDraftWriter(Protocol):
    def generate(
        self,
        *,
        name: str,
        request: SkillGenerateRequest,
        complexity: Literal["SIMPLE", "COMPLEX"],
        service_token: str,
        request_id: str,
    ) -> str: ...

    def revise(
        self,
        *,
        base_markdown: str,
        request: SkillReviseRequest,
        service_token: str,
        request_id: str,
    ) -> str: ...

    def repair(
        self,
        *,
        invalid_markdown: str,
        issues: list[ValidationIssue],
        service_token: str,
        request_id: str,
    ) -> str: ...


class TemplateSkillDraftWriter:
    def generate(
        self,
        *,
        name: str,
        request: SkillGenerateRequest,
        complexity: Literal["SIMPLE", "COMPLEX"],
        service_token: str,
        request_id: str,
    ) -> str:
        del service_token, request_id
        return (
            _render_complex_skill(name, request)
            if complexity == "COMPLEX"
            else _render_simple_skill(name, request)
        )

    def revise(
        self,
        *,
        base_markdown: str,
        request: SkillReviseRequest,
        service_token: str,
        request_id: str,
    ) -> str:
        del service_token, request_id
        return base_markdown.rstrip() + _revision_section(request)

    def repair(
        self,
        *,
        invalid_markdown: str,
        issues: list[ValidationIssue],
        service_token: str,
        request_id: str,
    ) -> str:
        del issues, service_token, request_id
        return invalid_markdown


class RequirementAnalyzer:
    def analyze(self, request: RequirementRequest) -> RequirementAnalysis:
        missing: list[str] = []
        if not request.expected_inputs:
            missing.append("expectedInputs")
        if not request.expected_outputs:
            missing.append("expectedOutputs")
        if not request.constraints:
            missing.append("constraints")
        complexity = self._complexity(request)
        return RequirementAnalysis(
            status="NEEDS_CLARIFICATION" if missing else "READY",
            complexity=complexity,
            normalizedGoal=" ".join(request.goal.split()),
            questions=[
                ClarificationQuestion(field=field, question=QUESTION_TEXT[field])
                for field in missing
            ],
            decisionSummary=(
                "需求信息尚不完整，必须先回答澄清问题。"
                if missing
                else "需求信息完整，可以生成Skill。"
            ),
        )

    @staticmethod
    def _complexity(request: RequirementRequest) -> str:
        complex_markers = ("跨系统", "多步骤", "审批", "并行", "mcp", "工具调用", "失败恢复")
        searchable = " ".join((request.goal, *request.constraints, *request.preferred_tools)).lower()
        return "COMPLEX" if (
            request.risk_level == "HIGH"
            or len(request.preferred_tools) > 1
            or bool(request.tool_references)
            or any(marker in searchable for marker in complex_markers)
        ) else "SIMPLE"


class SkillValidator:
    REQUIRED_SECTIONS = (
        "## Purpose",
        "## Required Inputs",
        "## Workflow",
        "## Constraints",
        "## Completion Criteria",
        "## Exception Handling",
    )

    def validate(self, markdown: str, *, require_mcp: bool = False) -> SkillValidation:
        issues: list[ValidationIssue] = []
        if not re.match(r"^---\nname: [a-z0-9-]+\ndescription: .+\n---\n", markdown):
            issues.append(ValidationIssue(code="INVALID_FRONTMATTER", message="frontmatter必须包含合法name和description"))
        for section in self.REQUIRED_SECTIONS:
            if section not in markdown:
                issues.append(ValidationIssue(code="MISSING_SECTION", message=f"缺少章节：{section}"))
        if require_mcp and "## MCP Tools" not in markdown:
            issues.append(ValidationIssue(code="MISSING_MCP_SECTION", message="复杂Skill必须声明MCP工具"))
        if "chain of thought" in markdown.lower() or "思维链" in markdown:
            issues.append(ValidationIssue(code="RAW_REASONING_FORBIDDEN", message="Skill不得要求输出模型原始思维链"))
        return SkillValidation(valid=not issues, issues=issues)


class SkillAuthoringService:
    def __init__(
        self,
        analyzer: RequirementAnalyzer,
        validator: SkillValidator,
        repository: SkillRepository,
        draft_writer: SkillDraftWriter | None = None,
    ) -> None:
        self._analyzer = analyzer
        self._validator = validator
        self._repository = repository
        self._draft_writer = draft_writer or TemplateSkillDraftWriter()

    def generate(
        self,
        request: SkillGenerateRequest,
        *,
        tenant_id: str,
        agent_id: str,
        idempotency_key: str,
        service_token: str = "",
        request_id: str = "planning-generate",
    ) -> SkillArtifact:
        analysis = self._analyzer.analyze(request.requirements)
        if analysis.status != "READY":
            raise RequirementClarificationRequired(analysis)
        fingerprint = hashlib.sha256(
            request.model_dump_json(by_alias=True).encode("utf-8")
        ).hexdigest()
        existing = self._repository.find_by_idempotency(
            tenant_id, agent_id, idempotency_key, fingerprint
        )
        if existing is not None:
            return existing
        skill_name = _skill_name(request.name)
        markdown = self._draft_writer.generate(
            name=skill_name,
            request=request,
            complexity=analysis.complexity,
            service_token=service_token,
            request_id=request_id,
        )
        validation = self._validator.validate(
            markdown,
            require_mcp=any(tool.protocol == "MCP" for tool in request.requirements.tool_references),
        )
        template_fallback = False
        if not validation.valid:
            markdown = self._draft_writer.repair(
                invalid_markdown=markdown,
                issues=validation.issues,
                service_token=service_token,
                request_id=f"{request_id}-repair",
            )
            validation = self._validator.validate(
                markdown,
                require_mcp=any(tool.protocol == "MCP" for tool in request.requirements.tool_references),
            )
        if not validation.valid:
            template_fallback = True
            markdown = TemplateSkillDraftWriter().generate(
                name=skill_name,
                request=request,
                complexity=analysis.complexity,
                service_token="",
                request_id=request_id,
            )
            validation = self._validator.validate(
                markdown,
                require_mcp=any(tool.protocol == "MCP" for tool in request.requirements.tool_references),
            )
        artifact = SkillArtifact(
            skillId=f"skill_{uuid4().hex}",
            version=1,
            name=skill_name,
            complexity=analysis.complexity,
            skillMarkdown=markdown,
            decisionSummary=(
                "模型草稿及自动修复未通过校验，已回退到安全标准模板。"
                if template_fallback
                else "需求完整并触发复杂模板，已加入工具声明、人工确认和失败升级规则。"
                if analysis.complexity == "COMPLEX"
                else "需求完整且未触发复杂模板规则，已生成标准Skill草稿。"
            ),
            validation=validation,
            createdAt=datetime.now(UTC),
        )
        self._repository.save_initial(
            artifact, tenant_id, agent_id, idempotency_key, fingerprint
        )
        return artifact

    def get(
        self, skill_id: str, version: int, *, tenant_id: str, agent_id: str
    ) -> SkillArtifact | None:
        return self._repository.get(skill_id, version, tenant_id, agent_id)

    def revise(
        self,
        skill_id: str,
        request: SkillReviseRequest,
        *,
        tenant_id: str,
        agent_id: str,
        idempotency_key: str,
        service_token: str = "",
        request_id: str = "planning-revise",
    ) -> SkillArtifact:
        base = self._repository.get(
            skill_id, request.base_version, tenant_id, agent_id
        )
        if base is None:
            raise KeyError("SKILL_VERSION_NOT_FOUND")
        fingerprint = hashlib.sha256(
            request.model_dump_json(by_alias=True).encode("utf-8")
        ).hexdigest()
        markdown = self._draft_writer.revise(
            base_markdown=base.skill_markdown,
            request=request,
            service_token=service_token,
            request_id=request_id,
        )
        artifact = SkillArtifact(
            skillId=base.skill_id,
            version=base.version + 1,
            name=base.name,
            complexity=base.complexity,
            skillMarkdown=markdown,
            decisionSummary=(
                f"基于{request.failure.error_code}失败摘要生成新版本；旧版本保持不可变。"
            ),
            validation=self._validator.validate(markdown),
            createdAt=datetime.now(UTC),
        )
        return self._repository.save_revision(
            artifact,
            tenant_id=tenant_id,
            agent_id=agent_id,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )


class RequirementClarificationRequired(Exception):
    def __init__(self, analysis: RequirementAnalysis) -> None:
        super().__init__("REQUIREMENT_CLARIFICATION_REQUIRED")
        self.analysis = analysis


def _revision_section(request: SkillReviseRequest) -> str:
    return f"""

## Revision Context

- Base version: {request.base_version}
- Failed step: {request.failure.failed_step}
- Error code: `{request.failure.error_code}`
- Failure summary: {request.failure.summary}
- Adjustment goal: {request.adjustment_goal}

执行新版本时先采用上述调整目标；如果仍超出Skill异常规则，必须再次暂停并请求人工或规划服务修订。
"""


def _skill_name(display_name: str) -> str:
    aliases = {
        "授信材料检查": "credit-material-check",
        "对公授信审查": "review-corporate-credit",
    }
    if display_name in aliases:
        return aliases[display_name]
    normalized = re.sub(r"[^a-z0-9]+", "-", display_name.lower()).strip("-")
    if normalized:
        return normalized[:63].rstrip("-")
    digest = hashlib.sha256(display_name.encode("utf-8")).hexdigest()[:10]
    return f"generated-skill-{digest}"


def _bullets(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def _render_simple_skill(name: str, request: SkillGenerateRequest) -> str:
    description = json.dumps(request.description, ensure_ascii=False)
    inputs = _bullets(request.requirements.expected_inputs)
    outputs = _bullets(request.requirements.expected_outputs)
    constraints = _bullets(request.requirements.constraints)
    return f"""---
name: {name}
description: {description}
---

# {request.name}

## Purpose

{request.requirements.goal}

## Required Inputs

{inputs}

## Workflow

1. 检查所有必需输入是否存在；缺失时停止并向用户询问。
2. 按目标处理输入，遵守全部约束。
3. 生成并复核约定输出。

## Constraints

{constraints}

## Completion Criteria

{outputs}

## Exception Handling

- 输入缺失：列出缺失项并暂停，等待用户补充。
- 规则冲突：停止处理，明确冲突规则并请求人工决定。
- 其他失败：只返回可审计的失败摘要。
"""


def _render_complex_skill(name: str, request: SkillGenerateRequest) -> str:
    description = json.dumps(request.description, ensure_ascii=False)
    inputs = _bullets(request.requirements.expected_inputs)
    outputs = _bullets(request.requirements.expected_outputs)
    constraints = _bullets(request.requirements.constraints)
    mcp_tools = [tool for tool in request.requirements.tool_references if tool.protocol == "MCP"]
    mcp_section = "\n".join(
        f"- `{tool.server}.{tool.tool}`：{tool.purpose}。调用前校验输入，调用后保存证据引用和状态。"
        for tool in mcp_tools
    ) or "- 当前没有指定MCP工具；执行前必须由上层智能体补充已授权工具。"
    workflow = "\n".join(
        f"{index}. 调用`{tool.server}.{tool.tool}`完成：{tool.purpose}；失败时进入异常规则。"
        for index, tool in enumerate(mcp_tools, start=2)
    )
    if not workflow:
        workflow = "2. 根据已授权工具清单逐步完成目标，不得猜测或调用未声明工具。"
    return f"""---
name: {name}
description: {description}
---

# {request.name}

## Purpose

{request.requirements.goal}

## Required Inputs

{inputs}

## MCP Tools

{mcp_section}

## Workflow

1. 校验输入、工具授权和约束；缺失时先向用户澄清。
{workflow}
{len(mcp_tools) + 2}. 汇总所有工具证据，生成约定输出并进入人工确认。

## Constraints

{constraints}

## Human Approval

- 高风险结论、规则冲突和不可逆动作必须暂停并请求人工确认。
- 未获得确认前只输出草稿，不执行任何业务动作。

## Completion Criteria

{outputs}

## Exception Handling

- 输入缺失：列出缺失项并暂停。
- 单个工具临时失败：仅按工具声明允许的次数重试，并记录状态。
- 工具返回冲突：停止合并结论，保留各自证据并请求人工判断。

## Failure Escalation

- Skill内规则可以处理的异常由上层智能体按本节执行。
- 超出规则边界时，向规划与推理引擎提交失败摘要和当前版本，请求生成新版本。
- 不得把原始模型思维过程作为失败上下文保存或返回。
"""
