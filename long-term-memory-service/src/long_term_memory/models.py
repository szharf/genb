from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MemoryScope = tuple[str, str, str]


class ExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    conversation_id: str = Field(alias="conversationId", min_length=1, max_length=128)
    turn_id: str = Field(alias="turnId", min_length=1, max_length=128)
    user_message: str = Field(alias="userMessage", min_length=1, max_length=32000)
    assistant_message: str = Field(alias="assistantMessage", max_length=64000)
    occurred_at: datetime = Field(alias="occurredAt")


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    query: str = Field(default="", max_length=16000)
    types: list[
        Literal["USER_PREFERENCE", "STABLE_FACT", "USER_CONSTRAINT"]
    ] | None = None
    source_types: list[Literal["CONVERSATION", "KNOWLEDGE_BASE"]] = Field(
        default_factory=lambda: ["CONVERSATION"],
        alias="sourceTypes",
        min_length=1,
    )
    top_k: int = Field(default=5, alias="topK", ge=1, le=100)


class DeleteMemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class CorrectMemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=4000)
    reason: str = Field(min_length=1, max_length=500)


class MemoryFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["CONFIRM", "REJECT"]
    reason: str = Field(min_length=1, max_length=500)


@dataclass(frozen=True)
class ExtractionJob:
    extraction_id: str
    scope: MemoryScope
    conversation_id: str
    turn_id: str
    user_message: str
    assistant_message: str
    occurred_at: datetime
    idempotency_hash: str
    request_fingerprint: str
    status: str
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    lease_until: datetime | None
    written_count: int
    rejected_count: int
    error_code: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LongTermMemoryRecord:
    memory_id: str
    scope: MemoryScope
    memory_type: str
    content: str
    content_hash: str
    confidence: float
    source_type: str
    source_ref: str
    status: str
    last_confirmed_at: datetime
    expires_at: datetime
    deleted_at: datetime | None
    deletion_reason: str | None
    deletion_actor: str | None
