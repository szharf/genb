from dataclasses import dataclass
import json
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
            content = self._structured_content or json.dumps({"memories": []})
        elif request.capability == "SESSION_SUMMARY":
            content = "Local-test summary of the visible completed conversation."
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
