import json
import math
from collections.abc import AsyncIterator
from typing import Any

from .models import (
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingUsage,
    EmbeddingVector,
    InferenceData,
    InferenceRequest,
    InferenceResponse,
    ResponseMeta,
    Usage,
)
from .errors import RuntimeProblem
from .provider import ModelProvider, ProviderFailure
from .schema import RestrictedJsonSchemaValidator, SchemaValidationError


class InferenceService:
    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider
        self._schema_validator = RestrictedJsonSchemaValidator()

    async def infer(
        self, request: InferenceRequest, request_id: str
    ) -> InferenceResponse:
        try:
            result = await self._provider.infer(request)
        except ProviderFailure as error:
            raise self._runtime_problem(error, request_id) from error
        structured = None
        if request.response_format is not None:
            try:
                structured = json.loads(result.content)
                self._schema_validator.validate(
                    structured, request.response_format.json_schema
                )
            except (json.JSONDecodeError, SchemaValidationError) as error:
                raise RuntimeProblem(
                    status=422,
                    code="MODEL_STRUCTURED_OUTPUT_INVALID",
                    title="Model structured output is invalid",
                    detail="The model output did not satisfy the requested JSON Schema.",
                    request_id=request_id,
                ) from error
        return InferenceResponse(
            data=InferenceData(
                content=result.content,
                structured=structured,
                model_alias=request.model_alias,
                model=result.model,
                provider=result.provider,
                usage=Usage(
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    total_tokens=result.input_tokens + result.output_tokens,
                    estimated=result.estimated,
                ),
                finish_reason=result.finish_reason,
            ),
            meta=ResponseMeta(
                request_id=request_id,
                component_code="INFERENCE_ENGINE",
                implementation_code="runtime-inference-fake",
                interface_version="1.0.0",
                degraded=False,
            ),
        )

    async def embed(
        self, request: EmbeddingRequest, request_id: str
    ) -> EmbeddingResponse:
        try:
            result = await self._provider.embed(request)
        except ProviderFailure as error:
            raise self._runtime_problem(error, request_id) from error
        if (
            len(result.vectors) != len(request.inputs)
            or any(len(vector) != request.dimensions for vector in result.vectors)
            or any(
                not math.isfinite(value)
                for vector in result.vectors
                for value in vector
            )
        ):
            raise RuntimeProblem(
                status=502,
                code="MODEL_PROVIDER_BAD_RESPONSE",
                title="Model provider returned an invalid response",
                detail="The embedding result shape or values are invalid.",
                request_id=request_id,
                retryable=True,
            )
        return EmbeddingResponse(
            data=EmbeddingData(
                vectors=[
                    EmbeddingVector(index=index, embedding=vector)
                    for index, vector in enumerate(result.vectors)
                ],
                model_alias=request.model_alias,
                model=result.model,
                provider=result.provider,
                dimensions=request.dimensions,
                usage=EmbeddingUsage(
                    input_tokens=result.input_tokens,
                    estimated=result.estimated,
                ),
            ),
            meta=ResponseMeta(
                request_id=request_id,
                component_code="INFERENCE_ENGINE",
                implementation_code="runtime-inference-fake",
                interface_version="1.0.0",
                degraded=False,
            ),
        )

    async def stream_events(
        self, request: InferenceRequest, request_id: str
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        sequence = 1
        yield "response.started", {
            "sequence": sequence,
            "requestId": request_id,
            "modelAlias": request.model_alias,
        }
        output_tokens = 0
        try:
            async for chunk in self._provider.stream(request):
                sequence += 1
                output_tokens += len(chunk.content)
                yield "response.delta", {
                    "sequence": sequence,
                    "requestId": request_id,
                    "content": chunk.content,
                }
        except ProviderFailure as error:
            sequence += 1
            yield "response.error", {
                "sequence": sequence,
                "requestId": request_id,
                "code": error.code,
                "detail": error.detail,
                "retryable": error.retryable,
            }
            return
        sequence += 1
        yield "response.usage", {
            "sequence": sequence,
            "requestId": request_id,
            "outputTokens": output_tokens,
            "estimated": True,
        }
        sequence += 1
        yield "response.completed", {
            "sequence": sequence,
            "requestId": request_id,
            "finishReason": "STOP",
        }

    @staticmethod
    def _runtime_problem(
        error: ProviderFailure, request_id: str
    ) -> RuntimeProblem:
        return RuntimeProblem(
            status=error.status,
            code=error.code,
            title=error.title,
            detail=error.detail,
            request_id=request_id,
            retryable=error.retryable,
        )
