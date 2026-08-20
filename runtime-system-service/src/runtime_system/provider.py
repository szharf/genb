from dataclasses import dataclass
import json
import re
from collections.abc import AsyncIterator
from typing import Protocol

from .models import EmbeddingRequest, InferenceRequest


@dataclass(frozen=True)
class ProviderInferenceResult:
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    finish_reason: str = "STOP"
    estimated: bool = True


@dataclass(frozen=True)
class ProviderEmbeddingResult:
    vectors: list[list[float]]
    model: str
    provider: str
    input_tokens: int
    estimated: bool = True


@dataclass(frozen=True)
class ProviderStreamChunk:
    content: str


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    status: str


class ProviderFailure(Exception):
    def __init__(
        self,
        *,
        status: int,
        code: str,
        title: str,
        detail: str,
        retryable: bool,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.retryable = retryable


class ModelProvider(Protocol):
    async def infer(self, request: InferenceRequest) -> ProviderInferenceResult: ...

    async def embed(self, request: EmbeddingRequest) -> ProviderEmbeddingResult: ...

    def stream(self, request: InferenceRequest) -> AsyncIterator[ProviderStreamChunk]: ...

    async def health(self) -> ProviderHealth: ...

    def models(self) -> list[dict[str, object]]: ...


class FakeModelProvider:
    def __init__(
        self,
        *,
        structured_content: str | None = None,
        embedding_vectors: list[list[float]] | None = None,
    ) -> None:
        self._structured_content = structured_content
        self._embedding_vectors = embedding_vectors

    async def infer(self, request: InferenceRequest) -> ProviderInferenceResult:
        user_content = next(
            message.content
            for message in reversed(request.messages)
            if message.role == "user"
        )
        if request.response_format is not None:
            content = self._structured_content or _fake_structured_content(request, user_content)
        elif request.capability == "SESSION_SUMMARY":
            content = "Local-test summary of the visible completed conversation."
        elif request.capability == "AGENT_CHAT":
            content = _fake_agent_chat(request)
        elif request.capability == "SKILL_REQUIREMENT_ANALYSIS":
            content = _fake_requirement_analysis(user_content)
        elif request.capability == "SKILL_AUTHORING":
            content = _fake_skill(user_content)
        else:
            content = user_content
        token_estimate = len(user_content)
        return ProviderInferenceResult(
            content=content,
            model="fake-chat-v1",
            provider="FAKE",
            input_tokens=token_estimate,
            output_tokens=token_estimate,
        )

    async def embed(self, request: EmbeddingRequest) -> ProviderEmbeddingResult:
        vectors = self._embedding_vectors
        if vectors is None:
            vectors = []
            for input_index, text in enumerate(request.inputs):
                seed = sum(ord(character) for character in text) + input_index * 31
                vectors.append(
                    [
                        ((seed + dimension_index * 17) % 1000) / 1000
                        for dimension_index in range(request.dimensions)
                    ]
                )
        return ProviderEmbeddingResult(
            vectors=vectors,
            model="fake-embedding-v1",
            provider="FAKE",
            input_tokens=sum(len(text) for text in request.inputs),
        )

    async def stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[ProviderStreamChunk]:
        user_content = next(
            message.content
            for message in reversed(request.messages)
            if message.role == "user"
        )
        for character in user_content:
            yield ProviderStreamChunk(content=character)

    async def health(self) -> ProviderHealth:
        return ProviderHealth(provider="FAKE", status="UP")

    def models(self) -> list[dict[str, object]]:
        return [
            {
                "modelAlias": "chat-default",
                "capabilities": ["CHAT", "STREAM"],
                "status": "AVAILABLE",
            },
            {
                "modelAlias": "embedding-default",
                "capabilities": ["EMBEDDING"],
                "dimensions": [4],
                "status": "AVAILABLE",
            },
            {
                "modelAlias": "memory-extraction-default",
                "capabilities": ["CHAT", "JSON_SCHEMA"],
                "status": "AVAILABLE",
            },
        ]


def _fake_structured_content(request: InferenceRequest, user_content: str) -> str:
    if request.response_format and request.response_format.schema_name == "long_term_memory_extraction_v1":
        match = re.search(r"USER_MESSAGE:\s*(.*?)\s*ASSISTANT_FINAL:", user_content, re.DOTALL)
        memory = match.group(1).strip() if match else user_content.strip()
        return json.dumps({"memories": [{
            "type": "USER_PREFERENCE", "content": memory,
            "confidence": 0.95, "action": "UPSERT",
        }]}, ensure_ascii=False)
    return json.dumps({"memories": []})


def _fake_agent_chat(request: InferenceRequest) -> str:
    user_messages = [message.content for message in request.messages if message.role == "user"]
    current = user_messages[-1]
    skill_flow = ("skill" in current.lower() or "技能" in current) and any(
        word in current.lower() for word in ("生成", "创建", "编写", "设计", "generate", "create", "write")
    )
    skill_flow = skill_flow or any(
        message.role == "assistant" and "接下来请确认" in message.content
        for message in request.messages[-6:]
    )
    if skill_flow:
        value = {"intent": "CREATE_SKILL", "answer": "继续梳理需求", "skill": None}
    elif ("刚才" in current or "remember" in current.lower()) and len(user_messages) > 1:
        value = {"intent": "CHAT", "answer": f"你刚才告诉我：{user_messages[-2]}", "skill": None}
    else:
        value = {"intent": "CHAT", "answer": f"已收到：{current}", "skill": None}
    return json.dumps(value, ensure_ascii=False)


def _fake_requirement_analysis(user_content: str) -> str:
    try:
        request = json.loads(user_content)
    except json.JSONDecodeError:
        request = {}
    previous = request.get("previousDraft") if isinstance(request, dict) else None
    current = str(request.get("currentMessage") or "材料检查Skill") if isinstance(request, dict) else "材料检查Skill"
    ready = isinstance(previous, dict)
    draft = {
        "name": "材料检查Skill", "description": "核对业务材料并输出缺失项检查表。",
        "goal": "根据输入材料生成结构化缺失项检查结果。",
        "expectedInputs": ["待检查材料"], "expectedOutputs": ["Markdown缺失项检查表"],
        "constraints": ["不执行外部操作", "结果由人工确认"], "preferredTools": [],
        "toolReferences": [], "riskLevel": "LOW",
        "confirmedFacts": [{"field": "goal", "value": current, "source": "USER", "confirmed": True}],
        "candidateFacts": [], "unknownFields": [] if ready else ["expectedInputs", "expectedOutputs"],
        "conflicts": [], "askedQuestionIds": ["q-material-format"],
        "askedQuestions": ["请输入材料形式与期望输出格式。"],
    }
    questions = [] if ready else [{
        "questionId": "q-material-format", "field": "expectedInputs", "topic": "INPUT",
        "question": "请输入待检查材料的形式，以及希望输出表格还是JSON？",
        "reason": "需要确定输入和交付格式。", "inputHint": "例如：输入文本材料，输出Markdown检查表。",
        "required": True,
    }]
    return json.dumps({
        "status": "READY" if ready else "CLARIFYING", "complexity": "SIMPLE",
        "draft": draft, "questions": questions, "references": [],
        "decisionSummary": "需求已完整，可以生成Skill。" if ready else "已记录目标，还需确认输入与输出。",
    }, ensure_ascii=False)


def _fake_skill(user_content: str) -> str:
    match = re.search(r"Skill技术名称：([^\r\n]+)", user_content)
    name = match.group(1).strip() if match else "material-check"
    return (
        f"---\nname: {name}\ndescription: Check business materials and produce a review checklist.\n---\n\n"
        "## Purpose\n核对业务材料并生成检查结果。\n\n"
        "## Required Inputs\n- 待检查材料\n\n"
        "## Workflow\n1. 读取材料。\n2. 核对必填项。\n3. 输出缺失项。\n\n"
        "## Constraints\n- 不执行任何外部操作。\n- 最终结果由人工确认。\n\n"
        "## Completion Criteria\n- 输出完整的Markdown检查表。\n\n"
        "## Exception Handling\n- 材料不足时明确列出待补信息。"
    )
