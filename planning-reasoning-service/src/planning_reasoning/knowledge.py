from __future__ import annotations

from typing import Protocol

from .models import RequirementDraft


PlanningReference = dict[str, str | bool]


class PlanningKnowledgeProvider(Protocol):
    def search(
        self, *, draft: RequirementDraft | None, message: str
    ) -> list[PlanningReference]: ...


class ApprovedPlanningKnowledge:
    """Small, reviewed phase-one catalog; a Tool Registry adapter can replace it later."""

    _ENTRIES: tuple[tuple[set[str], PlanningReference], ...] = (
        (
            {"授信", "材料", "审单", "检查"},
            {
                "id": "skill-template-credit-document-check",
                "type": "SKILL_TEMPLATE",
                "name": "授信材料检查模板",
                "summary": "先确认材料范围和检查规则，再逐项输出缺失材料、异常原因和证据引用；不得修改原件。",
                "source": "GENB_APPROVED",
                "authorized": True,
            },
        ),
        (
            {"mcp", "接口", "api", "工具", "sdk"},
            {
                "id": "standard-authorized-tool-declaration",
                "type": "DEVELOPMENT_STANDARD",
                "name": "授权工具声明规范",
                "summary": "Skill只能声明已注册、已授权且具有明确参数契约的HTTP API、MCP或SDK；规划组件不执行工具。",
                "source": "GENB_APPROVED",
                "authorized": True,
            },
        ),
        (
            {"skill", "生成", "规划", "流程"},
            {
                "id": "standard-skill-markdown-structure",
                "type": "DEVELOPMENT_STANDARD",
                "name": "标准Skill文档结构",
                "summary": "SKILL.md frontmatter只包含name和description；正文使用命令式步骤，并按需包含输入、流程、约束、完成标准和异常处理。",
                "source": "GENB_APPROVED",
                "authorized": True,
            },
        ),
        (
            {"审批", "高风险", "授信", "转账", "不可逆"},
            {
                "id": "policy-human-approval",
                "type": "POLICY",
                "name": "高风险人工确认规则",
                "summary": "高风险结论、规则冲突、不可逆动作和越权请求必须暂停，保留摘要并请求授权人员确认。",
                "source": "GENB_APPROVED",
                "authorized": True,
            },
        ),
        (
            {"异常", "失败", "重试", "恢复"},
            {
                "id": "standard-skill-failure-escalation",
                "type": "DEVELOPMENT_STANDARD",
                "name": "Skill异常和重新规划规范",
                "summary": "Skill内规则先处理已知异常；超出规则边界时停止执行，并向规划组件提交失败摘要以生成新版本。",
                "source": "GENB_APPROVED",
                "authorized": True,
            },
        ),
    )

    def search(
        self, *, draft: RequirementDraft | None, message: str
    ) -> list[PlanningReference]:
        searchable = " ".join(
            (
                message,
                draft.goal if draft else "",
                " ".join(draft.expected_inputs) if draft else "",
                " ".join(draft.expected_outputs) if draft else "",
                " ".join(draft.constraints) if draft else "",
            )
        ).lower()
        ranked: list[tuple[int, int, PlanningReference]] = []
        for index, (keywords, reference) in enumerate(self._ENTRIES):
            score = sum(1 for keyword in keywords if keyword in searchable)
            if score:
                ranked.append((score, -index, reference))
        ranked.sort(reverse=True, key=lambda item: (item[0], item[1]))
        return [dict(item[2]) for item in ranked[:5]]
