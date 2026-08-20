import os
import logging
import hmac
import secrets
from collections.abc import AsyncIterator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, TypedDict
from urllib.parse import urlencode

import httpx
import redis.asyncio as redis_async
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from .clients import (
    GatewayBindingClient, GatewayCapabilityClient, GatewayLongTermMemoryClient,
    GatewayPlanningReasoningClient, GatewayRuntimeInferenceClient, GatewayShortTermMemoryClient,
)
from .conversations import RedisConversationStore
from .errors import RemoteCallError
from .orchestrator import CustomerCoreComponentAgent, DeterministicAnswerer, PlanningTestAgent, StandaloneMemoryTestAgent
from .settings import WebSettings
from .sessions import CustomerSession, RedisCustomerSessionStore


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
        str, StringConstraints(pattern=r"^(ANALYZE|CONVERSE|GENERATE|VALIDATE|REVISE)$")
    ]
    payload: dict[str, object]


class LongTermExtractionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: Identifier = Field(alias="sessionId")
    message: Annotated[str, StringConstraints(min_length=1, max_length=16000)]


class LongTermSearchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: Identifier = Field(alias="sessionId")
    query: Annotated[str, StringConstraints(max_length=16000)] = ""
    source_types: list[Literal["CONVERSATION", "KNOWLEDGE_BASE"]] = Field(
        alias="sourceTypes", min_length=1
    )


class ConversationMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    text: Annotated[str, StringConstraints(min_length=1, max_length=16000)]
    error: bool = False


class ConversationSnapshotRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scenario: Literal["short", "long", "skill"]
    title: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    task_id: Identifier = Field(alias="taskId")
    session_id: Identifier = Field(alias="sessionId")
    phase: Annotated[int, Field(ge=0, le=2)] = 0
    first_message: Annotated[str, StringConstraints(max_length=16000)] = Field(
        default="", alias="firstMessage"
    )
    messages: Annotated[list[ConversationMessageRequest], Field(max_length=100)]
    suggestions: Annotated[list[str | dict[str, str]], Field(max_length=20)] = []
    evidence: dict[str, object] | None = None
    skill: dict[str, object] | None = None
    created_at: Annotated[str, StringConstraints(max_length=40)] = Field(
        default="", alias="createdAt"
    )


async def get_session_store() -> AsyncIterator[RedisCustomerSessionStore]:
    settings = WebSettings.from_mapping(os.environ)
    client = redis_async.Redis(
        host=os.environ.get("AGENT_REDIS_HOST", "127.0.0.1"),
        port=int(os.environ.get("AGENT_REDIS_PORT", "6379")),
        password=os.environ.get("AGENT_REDIS_PASSWORD") or None,
        decode_responses=True,
        socket_timeout=3,
    )
    try:
        yield RedisCustomerSessionStore(client, settings.agent_id, ttl_seconds=8 * 60 * 60)
    finally:
        await client.aclose()


async def get_conversation_store() -> AsyncIterator[RedisConversationStore]:
    settings = WebSettings.from_mapping(os.environ)
    client = redis_async.Redis(
        host=os.environ.get("AGENT_REDIS_HOST", "127.0.0.1"),
        port=int(os.environ.get("AGENT_REDIS_PORT", "6379")),
        password=os.environ.get("AGENT_REDIS_PASSWORD") or None,
        decode_responses=True,
        socket_timeout=3,
    )
    try:
        yield RedisConversationStore(client, settings.agent_id, ttl_seconds=90 * 24 * 60 * 60)
    finally:
        await client.aclose()


async def get_customer_session(
    request: Request,
    store: Annotated[RedisCustomerSessionStore, Depends(get_session_store)],
) -> CustomerSession:
    gateway = _gateway_subject(request)
    if gateway is not None:
        return gateway
    session = await store.get(request.cookies.get("genb_agent_session", ""))
    if session is None:
        raise HTTPException(status_code=401, detail="智能体会话缺失或已过期")
    return session


def _gateway_subject(request: Request) -> CustomerSession | None:
    token = request.headers.get("X-GenB-Identity-Token", "")
    user_id = request.headers.get("X-GenB-User-Id", "")
    agent_id = request.headers.get("X-GenB-Agent-Id", "")
    expected_agent = os.environ.get("AGENT_ID", "")
    if not token or not user_id or not agent_id or not hmac.compare_digest(agent_id, expected_agent):
        return None
    try:
        numeric_user_id = int(user_id)
    except ValueError:
        return None
    return CustomerSession(token, agent_id, numeric_user_id, user_id)


class AgentSsoClient:
    def __init__(self, http: httpx.AsyncClient, settings: WebSettings) -> None:
        self._http = http
        self._settings = settings

    async def exchange(self, *, code: str, state: str) -> CustomerSession:
        callback_url = os.environ.get("AGENT_CALLBACK_URL", "http://localhost:18714/auth/callback")
        response = await self._http.post(
            f"{self._settings.genb_base_url.rstrip('/')}/v1/client/agents/{self._settings.agent_id}/sso/token",
            headers={"X-Agent-Credential": self._settings.service_credential},
            json={"code": code, "callbackUrl": callback_url, "state": state},
        )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="智能体授权无效，请重新登录")
        payload = response.json()
        data = payload.get("data", payload)
        return CustomerSession(
            session_grant=str(data["sessionGrant"]),
            agent_id=str(data["agentId"]),
            user_id=int(data["userId"]),
            username=str(data["username"]),
        )

    async def logout(self, *, session_grant: str) -> None:
        response = await self._http.post(
            f"{self._settings.genb_base_url.rstrip('/')}/v1/client/agents/{self._settings.agent_id}/sso/logout",
            headers={"X-Agent-Credential": self._settings.service_credential},
            json={"sessionGrant": session_grant},
        )
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="智能体会话撤销失败，请稍后重试")


async def get_sso_client() -> AsyncIterator[AgentSsoClient]:
    settings = WebSettings.from_mapping(os.environ)
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
        yield AgentSsoClient(http, settings)


async def get_agent(
    x_genb_identity_token: Annotated[str, Header(alias="X-GenB-Identity-Token")],
) -> AsyncIterator[StandaloneMemoryTestAgent]:
    settings = WebSettings.from_mapping(os.environ)
    gateway_url = os.environ.get("DATA_PLANE_GATEWAY_URL", "http://127.0.0.1:9080")
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
        gateway = GatewayCapabilityClient(http, gateway_url, identity_token=x_genb_identity_token,
                                          agent_credential=settings.service_credential)
        yield StandaloneMemoryTestAgent(
            agent_id=settings.agent_id,
            service_credential=settings.service_credential,
            genb=GatewayBindingClient(gateway_url),
            memory=GatewayShortTermMemoryClient(gateway),
            control=GatewayLongTermMemoryClient(gateway),
            answerer=DeterministicAnswerer(),
        )


async def get_planning_agent(
    x_genb_identity_token: Annotated[str, Header(alias="X-GenB-Identity-Token")],
) -> AsyncIterator[PlanningTestAgent]:
    settings = WebSettings.from_mapping(os.environ)
    gateway_url = os.environ.get("DATA_PLANE_GATEWAY_URL", "http://127.0.0.1:9080")
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
        gateway = GatewayCapabilityClient(http, gateway_url, identity_token=x_genb_identity_token,
                                          agent_credential=settings.service_credential)
        yield PlanningTestAgent(
            agent_id=settings.agent_id,
            service_credential=settings.service_credential,
            genb=GatewayBindingClient(gateway_url),
            planning=GatewayPlanningReasoningClient(gateway),
        )


async def get_customer_agent(
    x_genb_identity_token: Annotated[str, Header(alias="X-GenB-Identity-Token")],
) -> AsyncIterator[CustomerCoreComponentAgent]:
    settings = WebSettings.from_mapping(os.environ)
    gateway_url = os.environ.get("DATA_PLANE_GATEWAY_URL", "http://127.0.0.1:9080")
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
        gateway = GatewayCapabilityClient(http, gateway_url, identity_token=x_genb_identity_token,
                                          agent_credential=settings.service_credential)
        yield CustomerCoreComponentAgent(
            agent_id=settings.agent_id,
            service_credential=settings.service_credential,
            genb=GatewayBindingClient(gateway_url),
            memory=GatewayShortTermMemoryClient(gateway),
            inference=GatewayRuntimeInferenceClient(gateway),
            planning=GatewayPlanningReasoningClient(gateway),
        )


def create_app() -> FastAPI:
    application = FastAPI(title="GenB Core Component Agent", version="1.0.0")
    web_ui = Path(__file__).resolve().parent / "web_ui"
    application.mount("/assets", StaticFiles(directory=web_ui), name="customer-agent-assets")

    @application.get("/", include_in_schema=False)
    async def customer_page(
        request: Request,
        store: Annotated[RedisCustomerSessionStore, Depends(get_session_store)],
    ) -> Response:
        session = _gateway_subject(request)
        if session is None:
            session = await store.get(request.cookies.get("genb_agent_session", ""))
        if session is None:
            return RedirectResponse(url="/auth/login", status_code=303)
        return FileResponse(web_ui / "index.html")

    @application.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "UP"}

    @application.get("/api/session")
    async def customer_session(
        session: Annotated[CustomerSession, Depends(get_customer_session)],
    ) -> dict[str, object]:
        return {"data": {
            "agentId": session.agent_id,
            "userId": session.user_id,
            "username": session.username,
        }}

    @application.get("/api/conversations")
    async def list_conversations(
        scenario: Literal["short", "long", "skill"],
        session: Annotated[CustomerSession, Depends(get_customer_session)],
        store: Annotated[RedisConversationStore, Depends(get_conversation_store)],
    ) -> dict[str, object]:
        return {"data": await store.list(session.user_id, scenario)}

    @application.put("/api/conversations/{conversation_id}", status_code=204)
    async def save_conversation(
        conversation_id: Identifier,
        request: ConversationSnapshotRequest,
        session: Annotated[CustomerSession, Depends(get_customer_session)],
        store: Annotated[RedisConversationStore, Depends(get_conversation_store)],
    ) -> Response:
        now = datetime.now(UTC).isoformat()
        conversation = request.model_dump(by_alias=True)
        conversation["conversationId"] = conversation_id
        conversation["createdAt"] = request.created_at or now
        conversation["updatedAt"] = now
        await store.save(session.user_id, conversation)
        return Response(status_code=204)

    @application.get("/auth/login", include_in_schema=False)
    async def auth_login() -> RedirectResponse:
        settings = WebSettings.from_mapping(os.environ)
        state = secrets.token_urlsafe(32)
        callback_url = os.environ.get("AGENT_CALLBACK_URL", "http://localhost:18714/auth/callback")
        portal_url = os.environ.get("PORTAL_AGENT_SSO_URL", "http://localhost:9100/agent-sso")
        location = f"{portal_url}?{urlencode({
            'agentId': settings.agent_id,
            'callbackUrl': callback_url,
            'state': state,
        })}"
        response = RedirectResponse(url=location, status_code=303)
        response.set_cookie(
            "genb_agent_login_state",
            state,
            httponly=True,
            secure=os.environ.get("AGENT_COOKIE_SECURE", "false").lower() == "true",
            samesite="lax",
            path="/",
            max_age=300,
        )
        return response

    @application.get("/auth/callback", include_in_schema=False)
    async def auth_callback(
        request: Request,
        code: str,
        state: str,
        store=Depends(get_session_store),
        sso: Annotated[AgentSsoClient, Depends(get_sso_client)] = None,
    ) -> RedirectResponse:
        expected_state = request.cookies.get("genb_agent_login_state", "")
        if not expected_state or not hmac.compare_digest(expected_state, state):
            raise HTTPException(status_code=400, detail="SSO state校验失败")
        session = await sso.exchange(code=code, state=state)
        session_id = await store.create(session)
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            "genb_agent_session",
            session_id,
            httponly=True,
            secure=os.environ.get("AGENT_COOKIE_SECURE", "false").lower() == "true",
            samesite="lax",
            path="/",
            max_age=8 * 60 * 60,
        )
        response.delete_cookie("genb_agent_login_state", path="/")
        return response

    @application.post("/auth/logout", include_in_schema=False)
    async def auth_logout(
        request: Request,
        store=Depends(get_session_store),
        sso: Annotated[AgentSsoClient, Depends(get_sso_client)] = None,
    ) -> RedirectResponse:
        session_id = request.cookies.get("genb_agent_session", "")
        session = await store.get(session_id)
        if session is not None:
            await sso.logout(session_grant=session.session_grant)
            await store.delete(session_id)
        response = RedirectResponse(
            url=os.environ.get(
                "PORTAL_AGENT_LOGOUT_URL",
                "http://localhost:9100/agent-sso/logout",
            ),
            status_code=303,
        )
        response.delete_cookie("genb_agent_session", path="/")
        return response

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
        session: Annotated[CustomerSession, Depends(get_customer_session)],
    ) -> dict[str, object]:
        try:
            result = await agent.chat(
                session_grant=session.session_grant,
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
            detail = (
                "智能体尚未绑定所需核心组件，请联系管理员完成绑定"
                if status_code == 403
                else "规划或模型服务暂时不可用，请稍后重试"
            )
            raise HTTPException(status_code=status_code, detail=detail) from error
        return {
            "data": {
                "agentId": WebSettings.from_mapping(os.environ).agent_id,
                "taskId": request.task_id,
                "sessionId": request.session_id,
                "answer": result.answer,
                "mode": result.mode,
                "skill": result.skill,
                "planning": result.planning,
                "committed": result.committed,
                "diagnostics": asdict(result.diagnostics),
            }
        }

    @application.post("/api/component-tests/short-term")
    async def short_term_component_test(
        request: ChatRequest,
        agent: Annotated[StandaloneMemoryTestAgent, Depends(get_agent)],
        session: Annotated[CustomerSession, Depends(get_customer_session)],
    ) -> dict[str, object]:
        try:
            result = await agent.chat(
                session_grant=session.session_grant,
                task_id=request.task_id,
                session_id=request.session_id,
                message=request.message,
            )
        except RemoteCallError as error:
            status_code = error.status_code if error.status_code in {401, 403, 404} else 502
            raise HTTPException(
                status_code=status_code, detail="短期记忆组件测试失败"
            ) from error
        return {"data": {
            "componentCode": "SHORT_TERM_MEMORY",
            "taskId": request.task_id,
            "sessionId": request.session_id,
            "answer": result.answer,
            "contextMessageCount": result.context_message_count,
            "committed": result.committed,
            "warnings": list(result.warnings),
        }}

    @application.post("/api/component-tests/long-term/extractions")
    async def long_term_extraction_test(
        request: LongTermExtractionRequest,
        agent: Annotated[StandaloneMemoryTestAgent, Depends(get_agent)],
        session: Annotated[CustomerSession, Depends(get_customer_session)],
    ) -> dict[str, object]:
        try:
            result = await agent.store_long_term(
                session_grant=session.session_grant,
                session_id=request.session_id,
                message=request.message,
            )
        except RemoteCallError as error:
            status_code = error.status_code if error.status_code in {401, 403, 404} else 502
            raise HTTPException(
                status_code=status_code, detail="长期记忆提取测试失败"
            ) from error
        return {"data": {
            "componentCode": "LONG_TERM_MEMORY",
            "extractionId": result.extraction_id,
            "status": result.status,
            "writtenCount": result.written_count,
            "rejectedCount": result.rejected_count,
        }}

    @application.post("/api/component-tests/long-term/search")
    async def long_term_search_test(
        request: LongTermSearchRequest,
        agent: Annotated[StandaloneMemoryTestAgent, Depends(get_agent)],
        session: Annotated[CustomerSession, Depends(get_customer_session)],
    ) -> dict[str, object]:
        try:
            items = await agent.recall_long_term(
                session_grant=session.session_grant,
                session_id=request.session_id,
                query=request.query,
                source_types=tuple(request.source_types),
            )
        except RemoteCallError as error:
            status_code = error.status_code if error.status_code in {401, 403, 404} else 502
            raise HTTPException(
                status_code=status_code, detail="长期记忆检索测试失败"
            ) from error
        return {"data": {
            "componentCode": "LONG_TERM_MEMORY",
            "items": [
                {
                    "memoryId": item.memory_id,
                    "type": item.memory_type,
                    "content": item.content,
                    "confidence": item.confidence,
                    "sourceType": item.source_type,
                    "sourceRef": item.source_ref,
                }
                for item in items
            ],
        }}

    @application.post("/api/component-tests/planning")
    async def planning_component_test(
        request: PlanningRequest,
        agent: Annotated[PlanningTestAgent, Depends(get_planning_agent)],
        session: Annotated[CustomerSession, Depends(get_customer_session)],
    ) -> dict[str, object]:
        try:
            result = await agent.invoke(
                session_grant=session.session_grant,
                session_id=request.session_id,
                operation=request.operation,
                payload=request.payload,
            )
        except RemoteCallError as error:
            status_code = error.status_code if error.status_code in {401, 403, 404, 409} else 502
            raise HTTPException(
                status_code=status_code, detail="规划与推理组件测试失败"
            ) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail="规划请求参数无效") from error
        return {"data": {
            "componentCode": "PLANNING_REASONING",
            "operation": request.operation,
            "result": result,
        }}

    return application


app = create_app()
