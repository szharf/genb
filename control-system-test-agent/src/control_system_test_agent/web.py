import os
import logging
from collections.abc import AsyncIterator
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, TypedDict

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from .clients import GenBClient, PlanningReasoningClient, RuntimeInferenceClient, StandaloneShortTermMemoryClient
from .errors import RemoteCallError
from .orchestrator import CustomerCoreComponentAgent, DeterministicAnswerer, PlanningTestAgent, StandaloneMemoryTestAgent
from .settings import WebSettings


logger = logging.getLogger(__name__)


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


async def get_customer_agent() -> AsyncIterator[CustomerCoreComponentAgent]:
    settings = WebSettings.from_mapping(os.environ)
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
        yield CustomerCoreComponentAgent(
            agent_id=settings.agent_id,
            service_credential=settings.service_credential,
            genb=GenBClient(http, settings.genb_base_url),
            memory=StandaloneShortTermMemoryClient(http),
            inference=RuntimeInferenceClient(http),
            planning=PlanningReasoningClient(http),
        )


def create_app() -> FastAPI:
    application = FastAPI(title="GenB Core Component Agent", version="1.0.0")
    web_ui = Path(__file__).resolve().parent / "web_ui"
    application.mount("/assets", StaticFiles(directory=web_ui), name="customer-agent-assets")

    @application.get("/", include_in_schema=False)
    def customer_page() -> FileResponse:
        return FileResponse(web_ui / "index.html")

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
            logger.warning(
                "memory test agent upstream failure operation=%s status=%s request_id=%s",
                error.operation,
                error.status_code,
                error.request_id,
            )
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

    @application.post("/api/customer/chat")
    async def customer_chat(
        request: ChatRequest,
        agent: Annotated[CustomerCoreComponentAgent, Depends(get_customer_agent)],
        authorization: Annotated[str, Header(alias="Authorization")] = "",
    ) -> dict[str, object]:
        if not authorization.startswith("Bearer ") or not authorization.removeprefix("Bearer ").strip():
            raise HTTPException(status_code=401, detail="请先从GenB登录后再使用智能体")
        try:
            result = await agent.chat(
                user_token=authorization.removeprefix("Bearer ").strip(),
                task_id=request.task_id,
                session_id=request.session_id,
                message=request.message,
            )
        except RemoteCallError as error:
            logger.warning(
                "customer agent upstream failure operation=%s status=%s request_id=%s",
                error.operation,
                error.status_code,
                error.request_id,
            )
            status_code = error.status_code if error.status_code in {401, 403, 404} else 502
            raise HTTPException(status_code=status_code, detail="智能体能力暂不可用，请联系管理员检查组件绑定") from error
        return {
            "data": {
                "agentId": WebSettings.from_mapping(os.environ).agent_id,
                "taskId": request.task_id,
                "sessionId": request.session_id,
                "answer": result.answer,
                "mode": result.mode,
                "skill": result.skill,
                "committed": result.committed,
                "diagnostics": asdict(result.diagnostics),
            }
        }

    return application


app = create_app()
