from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


@dataclass(frozen=True)
class ExtractionCandidate:
    memory_type: str
    content: str
    confidence: float


@dataclass(frozen=True)
class ExtractionModelResult:
    model: str
    candidates: tuple[ExtractionCandidate, ...]


class MemoryExtractionModel(Protocol):
    def extract(
        self, *, user_message: str, assistant_message: str
    ) -> ExtractionModelResult: ...


class RetryableExtractionError(Exception):
    pass


class InvalidExtractionOutput(Exception):
    pass


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
        client: httpx.Client,
        service_token: str,
        inference_url: str,
        model_alias: str,
    ) -> None:
        if len(service_token) < 16:
            raise ValueError("Runtime Inference token must contain at least 16 characters")
        self._client = client
        self._token = service_token
        self._url = inference_url
        self._model_alias = model_alias

    def extract(
        self, *, user_message: str, assistant_message: str
    ) -> ExtractionModelResult:
        try:
            response = self._client.post(
                self._url,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "X-Request-Id": f"req_ltm_{uuid4().hex}",
                },
                json={
                    "capability": "MEMORY_EXTRACTION",
                    "modelAlias": self._model_alias,
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
                                f"USER_MESSAGE:\n{user_message}\n\n"
                                f"ASSISTANT_FINAL:\n{assistant_message}"
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
            raise RetryableExtractionError from error
        if response.status_code in {429, 502, 503, 504}:
            raise RetryableExtractionError
        if response.status_code != 200 or len(response.content) > 131_072:
            raise InvalidExtractionOutput
        try:
            body = response.json()
            data = body.get("data") if isinstance(body, dict) else None
            structured = data.get("structured") if isinstance(data, dict) else None
            model = data.get("model") if isinstance(data, dict) else None
            if not isinstance(model, str) or not model:
                raise InvalidExtractionOutput
            payload = _ExtractionPayload.model_validate(structured)
        except (ValueError, ValidationError) as error:
            raise InvalidExtractionOutput from error
        return ExtractionModelResult(
            model=model,
            candidates=tuple(
                ExtractionCandidate(
                    memory_type=item.type,
                    content=item.content,
                    confidence=item.confidence,
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
