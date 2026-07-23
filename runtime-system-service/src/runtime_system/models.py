from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    role: Literal["system", "developer", "user", "assistant"]
    content: str = Field(min_length=1)


class ResponseFormat(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["JSON_SCHEMA"]
    schema_name: str = Field(alias="schemaName", min_length=1)
    json_schema: dict[str, Any] = Field(alias="jsonSchema")


class InferenceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    capability: str = Field(min_length=1)
    model_alias: str = Field(alias="modelAlias", min_length=1)
    messages: list[Message] = Field(min_length=1)
    response_format: ResponseFormat | None = Field(
        default=None, alias="responseFormat"
    )


class Usage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    input_tokens: int = Field(alias="inputTokens", ge=0)
    output_tokens: int = Field(alias="outputTokens", ge=0)
    total_tokens: int = Field(alias="totalTokens", ge=0)
    estimated: bool


class InferenceData(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    content: str
    structured: dict[str, Any] | list[Any] | None = None
    model_alias: str = Field(alias="modelAlias")
    model: str
    provider: str
    usage: Usage
    finish_reason: str = Field(alias="finishReason")


class ResponseMeta(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(alias="requestId")
    component_code: str = Field(alias="componentCode")
    implementation_code: str = Field(alias="implementationCode")
    interface_version: str = Field(alias="interfaceVersion")
    degraded: bool


class InferenceResponse(BaseModel):
    data: InferenceData
    meta: ResponseMeta


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    model_alias: str = Field(alias="modelAlias", min_length=1)
    inputs: list[str] = Field(min_length=1, max_length=128)
    dimensions: int = Field(ge=1, le=4096)
    purpose: str = Field(min_length=1)


class EmbeddingVector(BaseModel):
    index: int = Field(ge=0)
    embedding: list[float]


class EmbeddingUsage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    input_tokens: int = Field(alias="inputTokens", ge=0)
    estimated: bool


class EmbeddingData(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    vectors: list[EmbeddingVector]
    model_alias: str = Field(alias="modelAlias")
    model: str
    provider: str
    dimensions: int
    usage: EmbeddingUsage


class EmbeddingResponse(BaseModel):
    data: EmbeddingData
    meta: ResponseMeta
