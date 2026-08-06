import os
from typing import Annotated, Callable

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from redis import Redis

from .models import (
    CallerScope,
    ContextPrepareRequest,
    ContextPrepareResponse,
    Identifier,
    TaskWorkbenchResponse,
    TurnCommitRequest,
    TurnCommitResponse,
    WorkbenchUpdate,
)
from .service import InMemoryTaskStore, RedisTaskStore, ShortTermMemoryService
from .identity import (
    DevelopmentHeaderIdentityVerifier,
    GenBIdentityVerifier,
    IdentityProblem,
    InvocationIdentity,
)


app = FastAPI(
    title="GenB Short-term Memory Service",
    version="1.1.0",
    openapi_version="3.1.0",
)

def configured_memory() -> ShortTermMemoryService:
    store_type = os.getenv("SHORT_TERM_MEMORY_STORE", "in_memory").lower()
    if store_type == "in_memory":
        return ShortTermMemoryService(
            InMemoryTaskStore(),
            max_stored_messages=int(os.getenv("SHORT_TERM_MEMORY_MAX_STORED_MESSAGES", "200")),
        )
    if store_type != "redis":
        raise RuntimeError("SHORT_TERM_MEMORY_STORE must be in_memory or redis")
    client = Redis(
        host=os.getenv("SHORT_TERM_MEMORY_REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("SHORT_TERM_MEMORY_REDIS_PORT", "6379")),
        db=int(os.getenv("SHORT_TERM_MEMORY_REDIS_DB", "0")),
        password=os.getenv("SHORT_TERM_MEMORY_REDIS_PASSWORD") or None,
        decode_responses=False,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    return ShortTermMemoryService(
        RedisTaskStore(client, os.getenv("SHORT_TERM_MEMORY_REDIS_PREFIX", "genb:short-term-memory:v1")),
        max_stored_messages=int(os.getenv("SHORT_TERM_MEMORY_MAX_STORED_MESSAGES", "200")),
    )


memory = configured_memory()


def configured_identity_verifier() -> DevelopmentHeaderIdentityVerifier | GenBIdentityVerifier:
    mode = os.getenv("SHORT_TERM_MEMORY_AUTH_MODE", "development_headers").lower()
    if mode == "development_headers":
        return DevelopmentHeaderIdentityVerifier()
    if mode != "genb":
        raise RuntimeError("SHORT_TERM_MEMORY_AUTH_MODE must be development_headers or genb")
    genb_url = os.getenv("SHORT_TERM_MEMORY_GENB_URL", "http://127.0.0.1:8581/api").rstrip("/")
    return GenBIdentityVerifier(
        client=httpx.Client(timeout=2.0),
        jwks_url=f"{genb_url}/.well-known/jwks.json",
        introspection_url=f"{genb_url}/v1/internal/service-credentials:introspect",
        internal_token=os.getenv("SHORT_TERM_MEMORY_GENB_INTERNAL_TOKEN", ""),
        issuer=os.getenv("SHORT_TERM_MEMORY_ACTOR_ISSUER", "genb"),
        audience=os.getenv("SHORT_TERM_MEMORY_ACTOR_AUDIENCE", "control-system"),
    )


identity_verifier = configured_identity_verifier()


def caller_scope(
    required_scope: str,
    tenant_id: str,
    agent_id: str,
    user_id: str,
    authorization: str,
    actor_token: str,
    request_id: str,
) -> CallerScope:
    try:
        if isinstance(identity_verifier, DevelopmentHeaderIdentityVerifier):
            identity = identity_verifier.verify_headers(
                tenant_id=tenant_id, agent_id=agent_id, user_id=user_id
            )
        else:
            service_token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
            identity = identity_verifier.verify(
                service_token=service_token,
                actor_token=actor_token,
                required_component="SHORT_TERM_MEMORY",
                required_scope=required_scope,
                request_id=request_id,
            )
    except PermissionError as error:
        raise HTTPException(status_code=401, detail="调用身份无效") from error
    except IdentityProblem as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return CallerScope(
        tenant_id=identity.tenant_id,
        agent_id=identity.agent_id,
        user_id=identity.user_id,
    )


def require_scope(required_scope: str) -> Callable[..., CallerScope]:
    def dependency(
        tenant_id: Annotated[str, Header(alias="X-Tenant-Id")] = "",
        agent_id: Annotated[str, Header(alias="X-Agent-Id")] = "",
        user_id: Annotated[str, Header(alias="X-User-Id")] = "",
        authorization: Annotated[str, Header(alias="Authorization")] = "",
        actor_token: Annotated[str, Header(alias="X-GenB-Actor-Token")] = "",
        request_id: Annotated[str, Header(alias="X-Request-Id")] = "",
    ) -> CallerScope:
        return caller_scope(
            required_scope, tenant_id, agent_id, user_id,
            authorization, actor_token, request_id,
        )
    return dependency


read_scope = require_scope("component:short-term-memory:read")
write_scope = require_scope("component:short-term-memory:write")
delete_scope = require_scope("component:short-term-memory:delete")


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/health/ready", tags=["health"])
def ready() -> dict[str, str]:
    try:
        ready_status = memory.store.ready()
    except Exception as error:
        raise HTTPException(status_code=503, detail="短期记忆存储不可用") from error
    if not ready_status:
        raise HTTPException(status_code=503, detail="短期记忆存储不可用")
    return {"status": "UP", "store": memory.store.name}


@app.get("/version", tags=["health"], operation_id="getShortTermMemoryVersion")
def version() -> dict[str, str]:
    return {
        "componentCode": "SHORT_TERM_MEMORY",
        "implementationCode": "short-term-memory-service-v1",
        "interfaceVersion": "1.1.0",
        "serviceVersion": "0.1.0",
    }


@app.put(
    "/api/v1/short-term-memory/tasks/{task_id}",
    tags=["task-workbench"],
    operation_id="saveTaskWorkbench",
    summary="保存或更新跨会话任务工作台",
)
def save_task(
    task_id: Identifier,
    request: WorkbenchUpdate,
    scope: Annotated[CallerScope, Depends(write_scope)],
) -> TaskWorkbenchResponse:
    return {"data": memory.save_workbench(scope, task_id, request)}


@app.get(
    "/api/v1/short-term-memory/tasks/{task_id}",
    tags=["task-workbench"],
    operation_id="getTaskWorkbench",
    summary="读取跨会话任务工作台",
)
def get_task(
    task_id: Identifier,
    scope: Annotated[CallerScope, Depends(read_scope)],
) -> TaskWorkbenchResponse:
    task = memory.get_task(scope, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务工作台不存在")
    return {"data": task}


@app.delete(
    "/api/v1/short-term-memory/tasks/{task_id}",
    tags=["task-workbench"],
    status_code=204,
    operation_id="deleteTaskWorkbench",
    summary="删除任务工作台及短期上下文",
)
def delete_task(
    task_id: Identifier,
    scope: Annotated[CallerScope, Depends(delete_scope)],
) -> None:
    memory.delete_task(scope, task_id)


@app.post(
    "/api/v1/short-term-memory/turns:commit",
    tags=["conversation-memory"],
    operation_id="commitShortTermTurn",
    summary="提交一轮用户与智能体消息",
)
def commit_turn(
    request: TurnCommitRequest,
    scope: Annotated[CallerScope, Depends(write_scope)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
) -> TurnCommitResponse:
    try:
        return {"data": memory.commit_turn(scope, request, idempotency_key)}
    except ValueError as error:
        if str(error) == "IDEMPOTENCY_CONFLICT":
            raise HTTPException(status_code=409, detail="幂等键对应的请求内容不一致") from error
        raise


@app.post(
    "/api/v1/short-term-memory/context:prepare",
    tags=["conversation-memory"],
    operation_id="prepareShortTermContext",
    summary="为当前会话准备任务上下文",
)
def prepare_context(
    request: ContextPrepareRequest,
    scope: Annotated[CallerScope, Depends(read_scope)],
) -> ContextPrepareResponse:
    return {"data": memory.prepare_context(scope, request)}
