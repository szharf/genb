import os
from collections.abc import AsyncIterator
from typing import Annotated, TypedDict

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from .clients import GenBClient, StandaloneShortTermMemoryClient
from .errors import RemoteCallError
from .orchestrator import DeterministicAnswerer, StandaloneMemoryTestAgent
from .settings import WebSettings


Identifier = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: Identifier = Field(alias="taskId")
    session_id: Identifier = Field(alias="sessionId")
    message: Annotated[str, StringConstraints(min_length=1, max_length=16000)]


class ChatData(TypedDict):
    agentId: str
    taskId: str
    sessionId: str
    answer: str
    contextMessageCount: int
    committed: bool
    warnings: list[str]


async def get_agent() -> AsyncIterator[StandaloneMemoryTestAgent]:
    settings = WebSettings.from_mapping(os.environ)
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
        yield StandaloneMemoryTestAgent(
            agent_id=settings.agent_id,
            service_credential=settings.service_credential,
            genb=GenBClient(http, settings.genb_base_url),
            memory=StandaloneShortTermMemoryClient(http),
            answerer=DeterministicAnswerer(),
        )


def create_app() -> FastAPI:
    application = FastAPI(title="Standalone Memory Test Agent", version="1.0.0")

    @application.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "UP"}

    @application.post("/api/chat")
    async def chat(
        request: ChatRequest,
        agent: Annotated[StandaloneMemoryTestAgent, Depends(get_agent)],
        authorization: Annotated[str, Header(alias="Authorization")] = "",
    ) -> dict[str, ChatData]:
        if not authorization.startswith("Bearer ") or not authorization.removeprefix("Bearer ").strip():
            raise HTTPException(status_code=401, detail="用户登录凭证缺失")
        user_token = authorization.removeprefix("Bearer ").strip()
        try:
            result = await agent.chat(
                user_token=user_token,
                task_id=request.task_id,
                session_id=request.session_id,
                message=request.message,
            )
        except RemoteCallError as error:
            status_code = error.status_code if error.status_code in {401, 403, 404} else 502
            raise HTTPException(status_code=status_code, detail="智能体调用短期记忆失败") from error
        settings = WebSettings.from_mapping(os.environ)
        return {"data": {
            "agentId": settings.agent_id,
            "taskId": request.task_id,
            "sessionId": request.session_id,
            "answer": result.answer,
            "contextMessageCount": result.context_message_count,
            "committed": result.committed,
            "warnings": list(result.warnings),
        }}

    return application


app = create_app()
