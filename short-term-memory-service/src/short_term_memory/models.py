from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


Identifier = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]


class CallerScope(BaseModel):
    tenant_id: Identifier
    agent_id: Identifier
    user_id: Identifier


class ToolResult(BaseModel):
    tool: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    summary: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class WorkbenchUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["ACTIVE", "WAITING_MATERIAL", "PAUSED", "COMPLETED"]
    instructions: list[Annotated[str, StringConstraints(min_length=1, max_length=1000)]] = Field(
        default_factory=list, max_length=20
    )
    progress: Annotated[str, StringConstraints(max_length=4000)] = ""
    pending_materials: list[Annotated[str, StringConstraints(min_length=1, max_length=500)]] = Field(
        default_factory=list, alias="pendingMaterials", max_length=50
    )
    tool_results: list[ToolResult] = Field(default_factory=list, alias="toolResults", max_length=50)
    resume_checkpoint: Annotated[str, StringConstraints(max_length=2000)] = Field(
        default="", alias="resumeCheckpoint"
    )
    expires_in_seconds: int = Field(default=86400, alias="expiresInSeconds", ge=60, le=2_592_000)


class TurnCommitRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: Identifier = Field(alias="taskId")
    session_id: Identifier = Field(alias="sessionId")
    turn_id: Identifier = Field(alias="turnId")
    user_message: Annotated[str, StringConstraints(min_length=1, max_length=16000)] = Field(alias="userMessage")
    assistant_message: Annotated[str, StringConstraints(min_length=1, max_length=16000)] = Field(
        alias="assistantMessage"
    )
    occurred_at: datetime = Field(alias="occurredAt")


class ContextPrepareRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: Identifier = Field(alias="taskId")
    session_id: Identifier = Field(alias="sessionId")
    query: Annotated[str, StringConstraints(max_length=16000)] = ""
    max_messages: int = Field(default=20, alias="maxMessages", ge=1, le=100)


class WorkbenchSnapshot(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["ACTIVE", "WAITING_MATERIAL", "PAUSED", "COMPLETED"]
    instructions: list[str] = Field(default_factory=list)
    progress: str = ""
    pending_materials: list[str] = Field(default_factory=list, alias="pendingMaterials")
    tool_results: list[ToolResult] = Field(default_factory=list, alias="toolResults")
    resume_checkpoint: str = Field(default="", alias="resumeCheckpoint")


class TaskWorkbenchView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: Identifier = Field(alias="taskId")
    workbench: WorkbenchSnapshot
    expires_at: datetime = Field(alias="expiresAt")


class TaskWorkbenchResponse(BaseModel):
    data: TaskWorkbenchView


class TurnCommitView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: Identifier = Field(alias="taskId")
    message_count: int = Field(alias="messageCount", ge=0)
    replayed: bool


class TurnCommitResponse(BaseModel):
    data: TurnCommitView


class ContextMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    turn_id: Identifier = Field(alias="turnId")
    session_id: Identifier = Field(alias="sessionId")
    role: Literal["user", "assistant"]
    content: str
    occurred_at: datetime = Field(alias="occurredAt")


class ContextPrepareView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: Identifier = Field(alias="taskId")
    session_id: Identifier = Field(alias="sessionId")
    messages: list[ContextMessage]
    workbench: WorkbenchSnapshot | None


class ContextPrepareResponse(BaseModel):
    data: ContextPrepareView
