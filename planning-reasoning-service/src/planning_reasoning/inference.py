from __future__ import annotations

import json
from typing import Literal

import httpx

from .models import (
    RequirementConversationResult,
    RequirementDraft,
    SkillGenerateRequest,
    SkillReviseRequest,
    ValidationIssue,
)


class ModelAuthoringError(RuntimeError):
    pass


class RuntimeInferenceRequirementAnalyst:
    """Turn a natural-language planning conversation into a confirmed requirement draft."""

    def __init__(self, *, client: httpx.Client, model_alias: str) -> None:
        self._client = client
        self._model_alias = model_alias

    def analyze(
        self,
        *,
        previous: RequirementDraft | None,
        message: str,
        references: list[dict[str, str | bool]],
        service_token: str,
        request_id: str,
    ) -> RequirementConversationResult:
        system = (
            "你是GenB规划与推理组件中的Skill需求分析器。你的任务不是立即编写Skill，而是更新需求草稿，"
            "判断信息是否足够，并生成与当前业务有关的澄清问题。\n"
            "规则：\n"
            "1. 合并本轮消息和历史草稿，不得清空或改写用户已经确认的事实。\n"
            "2. 按语义理解用户表达，不依赖‘输入为’‘输出为’等固定句式。\n"
            "3. 模板、检索结果和模型推断只能作为候选，不得伪装成用户确认的信息。\n"
            "4. 已经回答过的问题不得重复；发现冲突时只询问冲突内容。\n"
            "5. 每轮最多询问3个真正影响行为、验收或安全的问题，问题要结合具体业务并提供回答示例。\n"
            "6. 低风险、目标和验收清晰且不需要外部工具时可以判定SIMPLE；多步骤、外部系统、MCP/API、"
            "审批、敏感数据、失败恢复或高风险业务判定COMPLEX。\n"
            "7. 不输出原始思维链，只输出一个合法JSON对象。\n"
            "JSON必须包含status、complexity、draft、questions、references、decisionSummary。"
            "status只能为CLARIFYING或READY。questions每项包含questionId、field、topic、question、reason、"
            "inputHint、required；topic只能为GOAL、INPUT、OUTPUT、WORKFLOW、RULE、TOOL、APPROVAL、EXCEPTION。"
            "draft必须完整包含name、description、goal、expectedInputs、expectedOutputs、constraints、"
            "preferredTools、toolReferences、riskLevel、confirmedFacts、candidateFacts、unknownFields、conflicts、"
            "askedQuestionIds和askedQuestions。riskLevel只能为LOW、MEDIUM或HIGH；无法判断时使用MEDIUM，"
            "把riskLevel加入unknownFields，将status设为CLARIFYING并询问用户确认。"
            "confirmedFacts必须记录field、value、source和confirmed，source只能"
            "是USER、SYSTEM、TEMPLATE或MODEL；只有USER且用户明确表达的事实才能confirmed=true。"
        )
        user = json.dumps(
            {
                "previousDraft": previous.model_dump(by_alias=True) if previous else None,
                "currentMessage": message,
                "approvedReferences": references,
            },
            ensure_ascii=False,
        )
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
                    "capability": "SKILL_REQUIREMENT_ANALYSIS",
                    "modelAlias": self._model_alias,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            if response.status_code != 200 or len(response.content) > 524_288:
                raise ModelAuthoringError("MODEL_ANALYSIS_UNAVAILABLE")
            content = response.json()["data"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ModelAuthoringError("MODEL_ANALYSIS_EMPTY")
            result = RequirementConversationResult.model_validate(
                _normalize_requirement_result(content)
            )
            if result.status == "READY" and result.questions:
                raise ModelAuthoringError("MODEL_ANALYSIS_INCONSISTENT")
            return result
        except ModelAuthoringError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ModelAuthoringError("MODEL_ANALYSIS_BAD_RESPONSE") from error


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


def _normalize_requirement_result(content: str) -> dict[str, object]:
    stripped = _strip_markdown_fence(content)
    decoder = json.JSONDecoder()
    payload: object | None = None
    for index, character in enumerate(stripped):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(stripped, index)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and "draft" in candidate:
            payload = candidate
            break
    if not isinstance(payload, dict):
        raise ValueError("MODEL_ANALYSIS_JSON_OBJECT_MISSING")

    draft = payload.get("draft")
    if isinstance(draft, dict):
        risk = str(draft.get("riskLevel") or "LOW").strip().upper()
        normalized_risk = {
            "低风险": "LOW", "低": "LOW",
            "中风险": "MEDIUM", "中": "MEDIUM",
            "高风险": "HIGH", "高": "HIGH",
        }.get(risk, risk)
        unresolved_risk = normalized_risk not in {"LOW", "MEDIUM", "HIGH"}
        draft["riskLevel"] = "MEDIUM" if unresolved_risk else normalized_risk
        for field in (
            "expectedInputs", "expectedOutputs", "constraints", "preferredTools",
            "unknownFields", "conflicts", "askedQuestionIds", "askedQuestions",
        ):
            draft[field] = _normalize_string_list(draft.get(field))
        if unresolved_risk:
            draft["unknownFields"] = list(dict.fromkeys([
                *draft["unknownFields"], "riskLevel",
            ]))
            payload["status"] = "CLARIFYING"
            raw_questions = payload.get("questions")
            questions = list(raw_questions) if isinstance(raw_questions, list) else []
            if not any(
                isinstance(question, dict) and question.get("field") == "riskLevel"
                for question in questions
            ):
                questions.insert(0, {
                    "questionId": "q-risk-level",
                    "field": "riskLevel",
                    "topic": "RULE",
                    "question": "这个Skill的风险等级应设为低、中还是高？",
                    "reason": "风险等级会影响人工审批、执行限制和异常升级规则。",
                    "inputHint": "例如：HIGH，高风险结论必须由人工确认。",
                    "required": True,
                })
            payload["questions"] = questions[:3]
        raw_tools = draft.get("toolReferences")
        draft["toolReferences"] = [
            item for item in raw_tools
            if isinstance(item, dict)
            and item.get("protocol") in {"MCP", "HTTP_API", "SDK"}
            and all(isinstance(item.get(key), str) and item[key].strip() for key in ("server", "tool", "purpose"))
        ] if isinstance(raw_tools, list) else []
        confirmed = draft.get("confirmedFacts")
        candidates = draft.get("candidateFacts")
        raw_confirmed = list(confirmed) if isinstance(confirmed, list) else []
        confirmed_list: list[object] = []
        candidate_list = list(candidates) if isinstance(candidates, list) else []
        retained_candidates: list[object] = []
        for fact in raw_confirmed:
            if (
                isinstance(fact, dict)
                and fact.get("source") == "USER"
                and fact.get("confirmed") is True
            ):
                confirmed_list.append(fact)
            else:
                retained_candidates.append(fact)
        for fact in candidate_list:
            if (
                isinstance(fact, dict)
                and fact.get("source") == "USER"
                and fact.get("confirmed") is True
            ):
                confirmed_list.append(fact)
            else:
                retained_candidates.append(fact)
        draft["confirmedFacts"] = confirmed_list
        draft["candidateFacts"] = retained_candidates

    references = payload.get("references")
    if isinstance(references, dict):
        approved = references.get("approvedReferences")
        payload["references"] = approved if isinstance(approved, list) else []
    return payload


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
            continue
        if not isinstance(item, dict):
            continue
        name = next(
            (str(item[key]).strip() for key in ("name", "field", "title", "value") if item.get(key)),
            "",
        )
        description = next(
            (str(item[key]).strip() for key in ("description", "reason", "detail") if item.get(key)),
            "",
        )
        text = "：".join(part for part in (name, description) if part)
        if text:
            normalized.append(text)
    return normalized
