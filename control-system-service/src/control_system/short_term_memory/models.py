from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CommitTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    turn_id: str = Field(alias="turnId", min_length=1, max_length=128)
    user_message: str = Field(alias="userMessage", min_length=1, max_length=32000)
    assistant_message: str = Field(alias="assistantMessage", max_length=64000)
    occurred_at: datetime = Field(alias="occurredAt")


class PrepareContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    query: str = Field(min_length=1, max_length=16000)
    max_context_tokens: int = Field(alias="maxContextTokens", ge=1, le=64000)


@dataclass(frozen=True)
class StoredMessage:
    turn_id: str
    role: Literal["user", "assistant"]
    content: str
    occurred_at: datetime


@dataclass(frozen=True)
class ConversationTurn:
    turn_id: str
    user_message: str
    assistant_message: str
    occurred_at: datetime


@dataclass(frozen=True)
class StoreCommitResult:
    turn_id: str
    duplicate: bool
    message_count: int


@dataclass(frozen=True)
class ConversationSummary:
    summary: str
    through_turn_id: str
    model: str
    updated_at: datetime


@dataclass(frozen=True)
class PreparedContext:
    messages: list[StoredMessage]
    trimmed_message_count: int
    estimated_token_count: int
    summary: ConversationSummary | None = None
    summary_status: str = "DISABLED"

    def __iter__(self):
        yield self.messages
        yield self.trimmed_message_count
        yield self.estimated_token_count
