import os
from typing import Annotated

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


app = FastAPI(
    title="GenB Short-term Memory Service",
    version="1.0.0",
    openapi_version="3.1.0",
)

def configured_memory() -> ShortTermMemoryService:
    store_type = os.getenv("SHORT_TERM_MEMORY_STORE", "in_memory").lower()
    if store_type == "in_memory":
        return ShortTermMemoryService(InMemoryTaskStore())
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
    return ShortTermMemoryService(RedisTaskStore(client, os.getenv("SHORT_TERM_MEMORY_REDIS_PREFIX", "genb:short-term-memory:v1")))


memory = configured_memory()


def caller_scope(
    tenant_id: Annotated[Identifier, Header(alias="X-Tenant-Id")],
    agent_id: Annotated[Identifier, Header(alias="X-Agent-Id")],
    user_id: Annotated[Identifier, Header(alias="X-User-Id")],
) -> CallerScope:
    return CallerScope(tenant_id=tenant_id, agent_id=agent_id, user_id=user_id)


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


@app.put(
    "/api/v1/short-term-memory/tasks/{task_id}",
    tags=["task-workbench"],
    operation_id="saveTaskWorkbench",
    summary="保存或更新跨会话任务工作台",
)
def save_task(
    task_id: Identifier,
    request: WorkbenchUpdate,
    scope: Annotated[CallerScope, Depends(caller_scope)],
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
    scope: Annotated[CallerScope, Depends(caller_scope)],
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
    scope: Annotated[CallerScope, Depends(caller_scope)],
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
    scope: Annotated[CallerScope, Depends(caller_scope)],
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
    scope: Annotated[CallerScope, Depends(caller_scope)],
) -> ContextPrepareResponse:
    return {"data": memory.prepare_context(scope, request)}
