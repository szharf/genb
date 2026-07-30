import os
from collections.abc import AsyncIterator
from typing import Annotated, TypedDict

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from .clients import GenBClient, PlanningReasoningClient, StandaloneShortTermMemoryClient
from .errors import RemoteCallError
from .orchestrator import DeterministicAnswerer, PlanningTestAgent, StandaloneMemoryTestAgent
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


class PlanningRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: Identifier = Field(alias="sessionId")
    operation: Annotated[
        str, StringConstraints(pattern=r"^(ANALYZE|GENERATE|VALIDATE|REVISE)$")
    ]
    payload: dict[str, object]


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


async def get_planning_agent() -> AsyncIterator[PlanningTestAgent]:
    settings = WebSettings.from_mapping(os.environ)
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
        yield PlanningTestAgent(
            agent_id=settings.agent_id,
            service_credential=settings.service_credential,
            genb=GenBClient(http, settings.genb_base_url),
            planning=PlanningReasoningClient(http),
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

    @application.post("/api/planning")
    async def planning(
        request: PlanningRequest,
        agent: Annotated[PlanningTestAgent, Depends(get_planning_agent)],
        authorization: Annotated[str, Header(alias="Authorization")] = "",
    ) -> dict[str, object]:
        if not authorization.startswith("Bearer ") or not authorization.removeprefix("Bearer ").strip():
            raise HTTPException(status_code=401, detail="用户登录凭证缺失")
        try:
            data = await agent.invoke(
                user_token=authorization.removeprefix("Bearer ").strip(),
                session_id=request.session_id,
                operation=request.operation,
                payload=request.payload,
            )
        except RemoteCallError as error:
            status_code = error.status_code if error.status_code in {401, 403, 404, 409} else 502
            raise HTTPException(status_code=status_code, detail="智能体调用规划与推理组件失败") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail="规划请求参数无效") from error
        return {"data": data}

    return application


app = create_app()
