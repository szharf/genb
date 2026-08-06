import os
from typing import Annotated

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException

from .identity import (
    DevelopmentHeaderIdentityVerifier,
    GenBIdentityVerifier,
    IdentityProblem,
    InvocationIdentity,
)
from .extraction import RuntimeInferenceExtractionModel
from .models import (
    CorrectMemoryRequest,
    DeleteMemoryRequest,
    ExtractionRequest,
    MemoryFeedbackRequest,
    SearchRequest,
)
from .postgres_repository import PostgreSQLConversationMemoryRepository
from .repository import InMemoryConversationMemoryRepository
from .service import (
    LongTermMemoryIdempotencyProblem,
    LongTermMemoryService,
    LongTermMemorySourceForbidden,
    LongTermMemorySourceUnavailable,
)


app = FastAPI(
    title="GenB Long-term Memory Service",
    version="1.0.0",
    openapi_version="3.1.0",
)


def configured_identity_verifier() -> DevelopmentHeaderIdentityVerifier | GenBIdentityVerifier:
    mode = os.getenv("LONG_TERM_MEMORY_AUTH_MODE", "development_headers").lower()
    if mode == "development_headers":
        return DevelopmentHeaderIdentityVerifier()
    if mode != "genb":
        raise RuntimeError("LONG_TERM_MEMORY_AUTH_MODE must be development_headers or genb")
    genb_url = os.getenv(
        "LONG_TERM_MEMORY_GENB_URL", "http://127.0.0.1:8581/api"
    ).rstrip("/")
    return GenBIdentityVerifier(
        client=httpx.Client(timeout=2.0),
        jwks_url=f"{genb_url}/.well-known/jwks.json",
        introspection_url=f"{genb_url}/v1/internal/service-credentials:introspect",
        internal_token=os.getenv("LONG_TERM_MEMORY_GENB_INTERNAL_TOKEN", ""),
        issuer=os.getenv("LONG_TERM_MEMORY_ACTOR_ISSUER", "genb"),
        audience=os.getenv("LONG_TERM_MEMORY_ACTOR_AUDIENCE", "control-system"),
    )


identity_verifier = configured_identity_verifier()


def configured_repository(
) -> InMemoryConversationMemoryRepository | PostgreSQLConversationMemoryRepository:
    dsn = os.getenv("LONG_TERM_MEMORY_POSTGRES_DSN", "").strip()
    if not dsn:
        return InMemoryConversationMemoryRepository()
    repository = PostgreSQLConversationMemoryRepository(dsn)
    if os.getenv("LONG_TERM_MEMORY_AUTO_MIGRATE", "false").lower() == "true":
        repository.ensure_schema()
    return repository


def configured_extraction_model() -> RuntimeInferenceExtractionModel | None:
    token = os.getenv("LONG_TERM_MEMORY_RUNTIME_TOKEN", "").strip()
    if not token:
        return None
    return RuntimeInferenceExtractionModel(
        client=httpx.Client(timeout=10.0),
        service_token=token,
        inference_url=os.getenv(
            "LONG_TERM_MEMORY_RUNTIME_URL",
            "http://127.0.0.1:18704/api/v1/runtime-system/inference",
        ),
        model_alias=os.getenv(
            "LONG_TERM_MEMORY_MODEL_ALIAS", "memory-extraction-default"
        ),
    )


conversation_memory_repository = configured_repository()
long_term_memory = LongTermMemoryService(
    conversation_memory_repository,
    extraction_model=configured_extraction_model(),
)


def require_identity(required_scope: str):
    def dependency(
        tenant_id: Annotated[str, Header(alias="X-Tenant-Id")] = "",
        agent_id: Annotated[str, Header(alias="X-Agent-Id")] = "",
        user_id: Annotated[str, Header(alias="X-User-Id")] = "",
        authorization: Annotated[str, Header(alias="Authorization")] = "",
        actor_token: Annotated[str, Header(alias="X-GenB-Actor-Token")] = "",
        request_id: Annotated[str, Header(alias="X-Request-Id")] = "",
    ) -> InvocationIdentity:
        try:
            if isinstance(identity_verifier, DevelopmentHeaderIdentityVerifier):
                return identity_verifier.verify_headers(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    user_id=user_id,
                )
            service_token = (
                authorization.removeprefix("Bearer ")
                if authorization.startswith("Bearer ")
                else ""
            )
            return identity_verifier.verify(
                service_token=service_token,
                actor_token=actor_token,
                required_component="LONG_TERM_MEMORY",
                required_scope=required_scope,
                request_id=request_id,
            )
        except IdentityProblem as error:
            raise HTTPException(status_code=error.status_code, detail=str(error)) from error

    return dependency


invocation_identity = require_identity("component:long-term-memory:write")
read_invocation_identity = require_identity("component:long-term-memory:read")
delete_invocation_identity = require_identity("component:long-term-memory:delete")


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/health/ready", tags=["health"])
def ready() -> dict[str, str]:
    store = (
        "POSTGRESQL"
        if isinstance(
            conversation_memory_repository, PostgreSQLConversationMemoryRepository
        )
        else "IN_MEMORY"
    )
    return {
        "status": "UP" if conversation_memory_repository.health() else "DOWN",
        "store": store,
    }


@app.get("/version", tags=["health"], operation_id="getLongTermMemoryVersion")
def version() -> dict[str, str]:
    return {
        "componentCode": "LONG_TERM_MEMORY",
        "implementationCode": "long-term-memory-service-v1",
        "interfaceVersion": "1.0.0",
        "serviceVersion": "0.1.0",
    }


@app.post("/api/v1/long-term-memory/extractions", status_code=202)
def request_extraction(
    request: ExtractionRequest,
    background_tasks: BackgroundTasks,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> dict[str, object]:
    try:
        job, duplicate = long_term_memory.request_extraction(
            identity, request, idempotency_key
        )
    except LongTermMemoryIdempotencyProblem as error:
        raise HTTPException(
            status_code=409, detail="幂等键已用于不同的提取请求"
        ) from error
    if not duplicate:
        background_tasks.add_task(
            long_term_memory.process_extraction, job.extraction_id
        )
    return {
        "data": {
            "extractionId": job.extraction_id,
            "status": job.status,
            "duplicate": duplicate,
        },
        "meta": {"componentCode": "LONG_TERM_MEMORY"},
    }


@app.get("/api/v1/long-term-memory/extractions/{extraction_id}")
def get_extraction(
    extraction_id: str,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
) -> dict[str, object]:
    job = long_term_memory.get_extraction(identity, extraction_id)
    if job is None:
        raise HTTPException(status_code=404, detail="长期记忆提取任务不存在")
    return {
        "data": {
            "extractionId": job.extraction_id,
            "status": job.status,
            "attemptCount": job.attempt_count,
            "writtenCount": job.written_count,
            "rejectedCount": job.rejected_count,
            "errorCode": job.error_code,
        },
        "meta": {"componentCode": "LONG_TERM_MEMORY"},
    }


@app.post("/api/v1/long-term-memory/memories:search")
def search_memories(
    request: SearchRequest,
    identity: Annotated[InvocationIdentity, Depends(read_invocation_identity)],
) -> dict[str, object]:
    try:
        outcome = long_term_memory.search(identity, request)
    except LongTermMemorySourceForbidden as error:
        raise HTTPException(status_code=403, detail="知识库来源无权访问") from error
    except LongTermMemorySourceUnavailable as error:
        raise HTTPException(status_code=503, detail="知识库来源当前不可用") from error
    meta: dict[str, object] = {"componentCode": "LONG_TERM_MEMORY"}
    if outcome.degraded_sources:
        meta["degradedSources"] = list(outcome.degraded_sources)
    return {
        "data": {
            "items": [
                {
                    "memoryId": item.memory_id,
                    "type": item.memory_type,
                    "content": item.content,
                    "confidence": item.confidence,
                    "sourceType": item.source_type,
                    "sourceRef": item.source_ref,
                    "lastConfirmedAt": item.last_confirmed_at.isoformat(),
                    "expiresAt": item.expires_at.isoformat(),
                }
                for item in outcome.items
            ],
            "appliedTopK": request.top_k,
        },
        "meta": meta,
    }


@app.delete("/api/v1/long-term-memory/memories/{memory_id}")
def delete_memory(
    memory_id: str,
    request: DeleteMemoryRequest,
    identity: Annotated[InvocationIdentity, Depends(delete_invocation_identity)],
) -> dict[str, object]:
    deleted = long_term_memory.delete_memory(
        identity,
        memory_id,
        reason=request.reason,
    )
    return {
        "data": {"deleted": deleted},
        "meta": {"componentCode": "LONG_TERM_MEMORY"},
    }


@app.post("/api/v1/long-term-memory/memories/{memory_id}:correct")
def correct_memory(
    memory_id: str,
    request: CorrectMemoryRequest,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
) -> dict[str, object]:
    corrected = long_term_memory.correct_memory(
        identity,
        memory_id,
        content=request.content,
        reason=request.reason,
    )
    if corrected is None:
        raise HTTPException(status_code=404, detail="长期记忆不存在或无法更正")
    return {
        "data": {
            "memoryId": corrected.memory_id,
            "supersededMemoryId": memory_id,
        },
        "meta": {"componentCode": "LONG_TERM_MEMORY"},
    }


@app.post("/api/v1/long-term-memory/memories/{memory_id}:feedback")
def record_memory_feedback(
    memory_id: str,
    request: MemoryFeedbackRequest,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
) -> dict[str, object]:
    updated = long_term_memory.record_feedback(
        identity,
        memory_id,
        action=request.action,
        reason=request.reason,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="长期记忆不存在或反馈已失效")
    return {
        "data": {
            "memoryId": updated.memory_id,
            "status": updated.status,
            "confidence": updated.confidence,
        },
        "meta": {"componentCode": "LONG_TERM_MEMORY"},
    }
