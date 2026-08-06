from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
import json
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import EmbeddingRequest, InferenceRequest
from .provider import (
    ModelProvider,
    ProviderEmbeddingResult,
    ProviderFailure,
    ProviderHealth,
    ProviderInferenceResult,
    ProviderStreamChunk,
)


class DirectProviderConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    provider_id: str = Field(alias="providerId", min_length=1)
    type: Literal["OPENAI_COMPATIBLE"]
    base_url: str = Field(alias="baseUrl", min_length=1)
    secret_ref: str = Field(alias="secretRef", min_length=1)
    timeout_ms: int = Field(alias="timeoutMs", ge=1, le=120000)
    structured_output_mode: Literal["JSON_SCHEMA", "JSON_OBJECT"] = Field(
        default="JSON_SCHEMA", alias="structuredOutputMode"
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        url = httpx.URL(value)
        if url.scheme not in {"http", "https"} or not url.host:
            raise ValueError("baseUrl must use http or https")
        if url.username or url.password:
            raise ValueError("baseUrl must not contain credentials")
        return value


class ModelRoute(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True, protected_namespaces=(), extra="forbid"
    )

    route_id: str = Field(alias="routeId", min_length=1)
    model_alias: str = Field(alias="modelAlias", min_length=1)
    capabilities: list[
        Literal["CHAT", "STREAM", "JSON_SCHEMA", "EMBEDDING"]
    ] = Field(min_length=1)
    provider_id: str = Field(alias="providerId", min_length=1)
    model: str = Field(min_length=1)
    dimensions: list[int] | None = None


class RoutingDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    schema_version: Literal["1.0"] = Field(alias="schemaVersion")
    providers: list[DirectProviderConfig] = Field(min_length=1)
    routes: list[ModelRoute] = Field(min_length=1)


class EnvironmentSecretResolver:
    def __init__(self, environment: Mapping[str, str]) -> None:
        self._environment = environment

    def resolve(self, secret_ref: str) -> str:
        prefix = "env://"
        if not secret_ref.startswith(prefix):
            raise ValueError("Direct Provider secretRef must use env://")
        variable_name = secret_ref.removeprefix(prefix)
        if (
            not variable_name
            or variable_name not in self._environment
            or not self._environment[variable_name]
        ):
            raise ValueError(f"Direct Provider secret is unavailable: {variable_name}")
        return self._environment[variable_name]


class OpenAICompatibleAdapter:
    def __init__(
        self,
        *,
        config: DirectProviderConfig,
        api_key: str,
        transport: httpx.AsyncBaseTransport | None,
    ) -> None:
        self._config = config
        self._api_key = api_key
        self._transport = transport

    async def infer(
        self, request: InferenceRequest, model: str
    ) -> ProviderInferenceResult:
        messages = [
            message.model_dump(mode="json") for message in request.messages
        ]
        if (
            request.response_format is not None
            and self._config.structured_output_mode == "JSON_OBJECT"
        ):
            schema = json.dumps(
                request.response_format.json_schema,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": (
                        "Return only one JSON object matching schema "
                        f"{request.response_format.schema_name}: {schema}"
                    ),
                },
            )
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if request.response_format is not None:
            if self._config.structured_output_mode == "JSON_OBJECT":
                payload["response_format"] = {"type": "json_object"}
            else:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": request.response_format.schema_name,
                        "strict": True,
                        "schema": request.response_format.json_schema,
                    },
                }
        response = await self._post("chat/completions", payload)
        try:
            body = response.json()
            choice = body["choices"][0]
            usage = body.get("usage") or {}
            return ProviderInferenceResult(
                content=choice["message"]["content"],
                model=body.get("model", model),
                provider=self._config.provider_id,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                finish_reason=str(
                    choice.get("finish_reason", "stop")
                ).upper(),
                estimated=False,
            )
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise self._bad_response() from error

    async def embed(
        self, request: EmbeddingRequest, model: str
    ) -> ProviderEmbeddingResult:
        payload = {
            "model": model,
            "input": request.inputs,
            "dimensions": request.dimensions,
        }
        response = await self._post("embeddings", payload)
        try:
            body = response.json()
            ordered_data = sorted(
                body["data"], key=lambda item: item["index"]
            )
            usage = body.get("usage") or {}
            return ProviderEmbeddingResult(
                vectors=[item["embedding"] for item in ordered_data],
                model=body.get("model", model),
                provider=self._config.provider_id,
                input_tokens=usage.get("prompt_tokens", 0),
                estimated=False,
            )
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise self._bad_response() from error

    async def stream(
        self, request: InferenceRequest, model: str
    ) -> AsyncIterator[ProviderStreamChunk]:
        payload = {
            "model": model,
            "messages": [
                message.model_dump(mode="json") for message in request.messages
            ],
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(
                base_url=self._config.base_url.rstrip("/") + "/",
                transport=self._transport,
                timeout=self._config.timeout_ms / 1000,
                headers={"Authorization": f"Bearer {self._api_key}"},
            ) as client:
                async with client.stream(
                    "POST", "chat/completions", json=payload
                ) as response:
                    self._raise_for_status(response)
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line.removeprefix("data:").strip()
                        if data == "[DONE]":
                            break
                        try:
                            body = json.loads(data)
                            content = body["choices"][0]["delta"].get(
                                "content"
                            )
                        except (
                            IndexError,
                            KeyError,
                            TypeError,
                            ValueError,
                        ) as error:
                            raise self._bad_response() from error
                        if content:
                            yield ProviderStreamChunk(content=content)
        except ProviderFailure:
            raise
        except httpx.TimeoutException as error:
            raise self._timeout_failure() from error
        except httpx.RequestError as error:
            raise self._unavailable_failure(
                "The selected model provider could not be reached."
            ) from error

    async def _post(
        self, endpoint: str, payload: dict[str, object]
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url=self._config.base_url.rstrip("/") + "/",
                transport=self._transport,
                timeout=self._config.timeout_ms / 1000,
                headers={"Authorization": f"Bearer {self._api_key}"},
            ) as client:
                response = await client.post(endpoint, json=payload)
        except httpx.TimeoutException as error:
            raise self._timeout_failure() from error
        except httpx.RequestError as error:
            raise self._unavailable_failure(
                "The selected model provider could not be reached."
            ) from error
        self._raise_for_status(response)
        return response

    @classmethod
    def _raise_for_status(cls, response: httpx.Response) -> None:
        if response.status_code == 429:
            raise ProviderFailure(
                status=429,
                code="MODEL_RATE_LIMITED",
                title="Model provider rate limit was reached",
                detail="The selected model provider temporarily rejected the request due to rate limiting.",
                retryable=True,
            )
        if response.status_code >= 500 or response.status_code in {401, 403}:
            raise cls._unavailable_failure(
                "The selected model provider is temporarily unavailable."
            )
        if response.status_code >= 400:
            raise ProviderFailure(
                status=400,
                code="MODEL_REQUEST_INVALID",
                title="Model request is invalid",
                detail="The selected model provider rejected the normalized request.",
                retryable=False,
            )

    @staticmethod
    def _bad_response() -> ProviderFailure:
        return ProviderFailure(
            status=502,
            code="MODEL_PROVIDER_BAD_RESPONSE",
            title="Model provider returned an invalid response",
            detail="The selected model provider returned a response that did not satisfy its published contract.",
            retryable=True,
        )

    @staticmethod
    def _timeout_failure() -> ProviderFailure:
        return ProviderFailure(
            status=504,
            code="MODEL_TIMEOUT",
            title="Model provider request timed out",
            detail="The selected model provider did not complete within the configured timeout.",
            retryable=True,
        )

    @staticmethod
    def _unavailable_failure(detail: str) -> ProviderFailure:
        return ProviderFailure(
            status=503,
            code="MODEL_PROVIDER_UNAVAILABLE",
            title="Model provider is unavailable",
            detail=detail,
            retryable=True,
        )


class ConfiguredModelProvider(ModelProvider):
    def __init__(
        self,
        *,
        routes: list[ModelRoute],
        adapters: Mapping[str, OpenAICompatibleAdapter],
    ) -> None:
        self._routes = {route.model_alias: route for route in routes}
        self._adapters = adapters

    async def infer(self, request: InferenceRequest) -> ProviderInferenceResult:
        route = self._routes.get(request.model_alias)
        required_capabilities = {"CHAT"}
        if request.response_format is not None:
            required_capabilities.add("JSON_SCHEMA")
        if route is None or not required_capabilities.issubset(
            route.capabilities
        ):
            raise ProviderFailure(
                status=503,
                code="MODEL_PROVIDER_UNAVAILABLE",
                title="Model provider is unavailable",
                detail="No published route is available for the requested model alias and capability.",
                retryable=True,
            )
        return await self._adapters[route.provider_id].infer(request, route.model)

    async def embed(self, request: EmbeddingRequest) -> ProviderEmbeddingResult:
        route = self._routes.get(request.model_alias)
        if route is None or "EMBEDDING" not in route.capabilities:
            raise ProviderFailure(
                status=503,
                code="MODEL_PROVIDER_UNAVAILABLE",
                title="Model provider is unavailable",
                detail="No published route is available for the requested model alias and capability.",
                retryable=True,
            )
        if (
            route.dimensions is not None
            and request.dimensions not in route.dimensions
        ):
            raise ProviderFailure(
                status=400,
                code="MODEL_REQUEST_INVALID",
                title="Model request is invalid",
                detail="The requested embedding dimension is not published for this model alias.",
                retryable=False,
            )
        return await self._adapters[route.provider_id].embed(
            request, route.model
        )

    async def stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[ProviderStreamChunk]:
        route = self._routes.get(request.model_alias)
        if route is None or "STREAM" not in route.capabilities:
            raise ProviderFailure(
                status=503,
                code="MODEL_PROVIDER_UNAVAILABLE",
                title="Model provider is unavailable",
                detail="No published route is available for the requested model alias and capability.",
                retryable=True,
            )
        async for chunk in self._adapters[route.provider_id].stream(
            request, route.model
        ):
            yield chunk

    async def health(self) -> ProviderHealth:
        provider = next(iter(self._adapters))
        return ProviderHealth(provider=provider, status="UP")

    def models(self) -> list[dict[str, object]]:
        catalog: list[dict[str, object]] = []
        for route in sorted(
            self._routes.values(), key=lambda item: item.model_alias
        ):
            item: dict[str, object] = {
                "modelAlias": route.model_alias,
                "capabilities": route.capabilities,
                "status": "AVAILABLE",
            }
            if route.dimensions is not None:
                item["dimensions"] = route.dimensions
            catalog.append(item)
        return catalog


def build_provider_from_document(
    document: object,
    *,
    environment: Mapping[str, str],
    transport: httpx.AsyncBaseTransport | None = None,
) -> ConfiguredModelProvider:
    config = RoutingDocument.model_validate(document)
    provider_ids: set[str] = set()
    for provider in config.providers:
        if provider.provider_id in provider_ids:
            raise ValueError(f"Duplicate providerId: {provider.provider_id}")
        provider_ids.add(provider.provider_id)
    aliases: set[str] = set()
    for route in config.routes:
        if route.model_alias in aliases:
            raise ValueError(f"Duplicate modelAlias: {route.model_alias}")
        aliases.add(route.model_alias)
        if route.provider_id not in provider_ids:
            raise ValueError(
                f"Route {route.route_id} references unknown providerId: {route.provider_id}"
            )
    secret_resolver = EnvironmentSecretResolver(environment)
    adapters = {
        provider.provider_id: OpenAICompatibleAdapter(
            config=provider,
            api_key=secret_resolver.resolve(provider.secret_ref),
            transport=transport,
        )
        for provider in config.providers
    }
    return ConfiguredModelProvider(routes=config.routes, adapters=adapters)
