from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import LongTermMemoryRuntimeConfig

MemoryScope = tuple[str, str, str]
MEMORY_SOURCE_TYPES = frozenset({"CONVERSATION", "KNOWLEDGE_BASE"})


class ExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    turn_id: str = Field(alias="turnId", min_length=1, max_length=128)
    user_message: str = Field(alias="userMessage", min_length=1, max_length=32000)
    assistant_message: str = Field(alias="assistantMessage", max_length=64000)
    occurred_at: datetime = Field(alias="occurredAt")


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    query: str = Field(default="", max_length=16000)
    types: list[Literal["USER_PREFERENCE", "STABLE_FACT", "USER_CONSTRAINT"]] | None = None
    source_types: list[Literal["CONVERSATION", "KNOWLEDGE_BASE"]] | None = Field(
        default=None, alias="sourceTypes", min_length=1
    )
    top_k: int | None = Field(default=None, alias="topK", ge=1, le=100)


class DeleteMemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=500)


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
    first_seen_at: datetime
    last_confirmed_at: datetime
    last_accessed_at: datetime | None
    expires_at: datetime


@dataclass(frozen=True)
class ExtractionJob:
    extraction_id: str
    scope: MemoryScope
    turn_id: str
    user_message: str
    assistant_message: str
    occurred_at: datetime
    idempotency_hash: str
    request_fingerprint: str
    config_version_id: int
    config: LongTermMemoryRuntimeConfig
    status: str
    attempt_count: int
    written_count: int
    rejected_count: int
    model: str | None
    error_code: str | None
    next_attempt_at: datetime
    lease_until: datetime | None
    created_at: datetime
    updated_at: datetime
