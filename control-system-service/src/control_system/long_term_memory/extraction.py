from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal


@dataclass(frozen=True)
class ExtractionCandidate:
    memory_type: str
    content: str
    confidence: float
    action: str


@dataclass(frozen=True)
class ExtractionModelRequest:
    user_message: str
    assistant_message: str
    model_alias: str
    request_id: str
    trace_parent: str | None = None
    capability: str = "MEMORY_EXTRACTION"


@dataclass(frozen=True)
class ExtractionModelResult:
    model: str
    candidates: tuple[ExtractionCandidate, ...]


class MemoryExtractionModel(Protocol):
    async def extract(self, request: ExtractionModelRequest) -> ExtractionModelResult: ...


class RetryableExtractionError(Exception):
    pass


class InvalidExtractionOutput(Exception):
    pass


class UnavailableExtractionModel:
    async def extract(self, request: ExtractionModelRequest) -> ExtractionModelResult:
        del request
        raise RuntimeError("Runtime Inference extraction adapter is not configured")


class _CandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["USER_PREFERENCE", "STABLE_FACT", "USER_CONSTRAINT"]
    content: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0, le=1)
    action: Literal["UPSERT"]


class _ExtractionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memories: list[_CandidatePayload] = Field(max_length=20)


class RuntimeInferenceExtractionModel:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        service_token: str,
        inference_url: str = "/api/v1/runtime-system/inference",
    ) -> None:
        if len(service_token) < 16:
            raise ValueError("Runtime Inference service token must contain at least 16 characters")
        self._client = client
        self._token = service_token
        self._url = inference_url

    async def extract(self, request: ExtractionModelRequest) -> ExtractionModelResult:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "X-Request-Id": request.request_id,
        }
        if request.trace_parent:
            headers["traceparent"] = request.trace_parent
        try:
            response = await self._client.post(
                self._url,
                headers=headers,
                json={
                "capability": request.capability,
                "modelAlias": request.model_alias,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Extract only explicit durable preferences, stable facts, and user constraints. "
                            "Never extract passwords, verification codes, tokens, API keys, hidden reasoning, "
                            "or one-time instructions. Return only the requested JSON schema."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"USER_MESSAGE:\n{request.user_message}\n\n"
                            f"ASSISTANT_FINAL:\n{request.assistant_message}"
                        ),
                    },
                ],
                "responseFormat": {
                    "type": "JSON_SCHEMA",
                    "schemaName": "long_term_memory_extraction_v1",
                    "jsonSchema": _extraction_schema(),
                },
                },
            )
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise RetryableExtractionError("Runtime Inference is temporarily unavailable") from error
        if response.status_code in {429, 502, 503, 504}:
            raise RetryableExtractionError("Runtime Inference is temporarily unavailable")
        if response.status_code != 200:
            raise InvalidExtractionOutput("Runtime Inference rejected extraction request")
        if len(response.content) > 131_072:
            raise InvalidExtractionOutput("Runtime Inference extraction response is too large")
        try:
            body = response.json()
        except ValueError as error:
            raise InvalidExtractionOutput("Runtime Inference extraction response is not JSON") from error
        data = body.get("data") if isinstance(body, dict) else None
        structured = data.get("structured") if isinstance(data, dict) else None
        model = data.get("model") if isinstance(data, dict) else None
        if not isinstance(model, str) or not model:
            raise InvalidExtractionOutput("Runtime Inference extraction response is invalid")
        try:
            payload = _ExtractionPayload.model_validate(structured)
        except ValidationError as error:
            raise InvalidExtractionOutput("Runtime Inference structured output is invalid") from error
        return ExtractionModelResult(
            model=model,
            candidates=tuple(
                ExtractionCandidate(
                    memory_type=item.type,
                    content=item.content,
                    confidence=item.confidence,
                    action=item.action,
                )
                for item in payload.memories
            ),
        )


def _extraction_schema() -> dict[str, object]:
    return {
        "type": "object",
        "required": ["memories"],
        "properties": {
            "memories": {
                "type": "array",
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "required": ["type", "content", "confidence", "action"],
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "USER_PREFERENCE",
                                "STABLE_FACT",
                                "USER_CONSTRAINT",
                            ],
                        },
                        "content": {"type": "string", "minLength": 1, "maxLength": 4000},
                        "confidence": {"type": "number"},
                        "action": {"type": "string", "enum": ["UPSERT"]},
                    },
                    "additionalProperties": False,
                },
            }
        },
        "additionalProperties": False,
    }
