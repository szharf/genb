from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
import json
import logging
import re
from time import monotonic
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, Header, Path, Request, Security, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from .errors import AuthenticationProblem, AuthorizationProblem, ControlSystemProblem
from .component_config import (
    ShortTermMemoryConfigProvider,
    ShortTermMemoryRuntimeConfig,
    StaticShortTermMemoryConfigProvider,
)
from .identity import IdentityVerifier, InvocationIdentity
from .short_term_memory.models import (
    CommitTurnRequest,
    ConversationTurn,
    PrepareContextRequest,
)
from .short_term_memory.service import ShortTermMemoryService
from .short_term_memory.store import SessionStore
from .summary import SummaryGenerator
from .telemetry import MetricsRegistry

COMPONENT_CODE = "SHORT_TERM_MEMORY"
IMPLEMENTATION_CODE = "control-memory-v1"
INTERFACE_VERSION = "1.0.0"
EVENT_LOGGER = logging.getLogger("control_system.events")
TRACE_PARENT_PATTERN = re.compile(
    r"^00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]$", re.IGNORECASE
)


def create_app(
    *,
    identity_verifier: IdentityVerifier,
    session_store: SessionStore,
    ttl_seconds: int = 86400,
    max_turns: int = 50,
    max_context_tokens: int = 64000,
    config_provider: ShortTermMemoryConfigProvider | None = None,
    summary_generator: SummaryGenerator | None = None,
    metrics: MetricsRegistry | None = None,
) -> FastAPI:
    app = FastAPI(title="GenB Control System", version="0.2.0")
    metric_registry = metrics or MetricsRegistry()
    metric_registry.ensure("short_term_context_hits_total")
    metric_registry.ensure("short_term_context_misses_total")
    memory = ShortTermMemoryService(
        session_store,
        config_provider=config_provider
        or StaticShortTermMemoryConfigProvider(
            ShortTermMemoryRuntimeConfig(
                ttl_seconds=ttl_seconds,
                max_turns=max_turns,
                max_context_tokens=max_context_tokens,
            )
        ),
        summary_generator=summary_generator,
        metrics=metric_registry,
    )
    app.state.metrics = metric_registry

    @app.middleware("http")
    async def measure_http(request: Request, call_next):
        started = monotonic()
        response = await call_next(request)
        route = request.scope.get("route")
        operation = getattr(route, "operation_id", None) or "unmatched"
        labels = {"operation": operation, "status": str(response.status_code)}
        metric_registry.increment("control_system_http_requests_total", labels)
        duration = monotonic() - started
        metric_registry.increment(
            "control_system_http_duration_seconds_sum", {"operation": operation}, duration
        )
        metric_registry.increment(
            "control_system_http_duration_seconds_count", {"operation": operation}
        )
        request_id = request.headers.get("X-Request-Id")
        trace_parent = request.headers.get("traceparent")
        EVENT_LOGGER.info(
            json.dumps(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "event": "control_system_http_completed",
                    "operation": operation,
                    "status": response.status_code,
                    "durationMs": round(duration * 1000, 3),
                    "requestId": request_id[:128] if request_id else None,
                    "traceId": (
                        trace_parent.split("-")[1]
                        if trace_parent and TRACE_PARENT_PATTERN.fullmatch(trace_parent)
                        else None
                    ),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return response
    service_credential_scheme = HTTPBearer(
        auto_error=False,
        scheme_name="ServiceCredential",
        description="GenB-issued service credential",
    )
    actor_token_scheme = APIKeyHeader(
        name="X-GenB-Actor-Token",
        auto_error=False,
        scheme_name="ActorToken",
        description="GenB-issued signed Actor Token",
    )

    @app.exception_handler(ControlSystemProblem)
    async def handle_control_problem(
        _request: Request, problem: ControlSystemProblem
    ) -> JSONResponse:
        return JSONResponse(
            status_code=problem.status,
            media_type="application/problem+json",
            content={
                "type": f"https://errors.genb.local/{problem.code.lower().replace('_', '-')}",
                "title": problem.title,
                "status": problem.status,
                "detail": problem.detail,
                "code": problem.code,
                "requestId": problem.request_id,
                "retryable": False,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_problem(
        request: Request, _problem: RequestValidationError
    ) -> JSONResponse:
        request_id = request.headers.get("X-Request-Id", "unknown")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            media_type="application/problem+json",
            content={
                "type": "https://errors.genb.local/control-request-invalid",
                "title": "Control System request is invalid",
                "status": 422,
                "detail": "The request did not satisfy the Short-term Memory Interface.",
                "code": "CONTROL_REQUEST_INVALID",
                "requestId": request_id,
                "retryable": False,
            },
        )

    def require_identity(required_scope: str) -> Callable[..., InvocationIdentity]:
        def verify(
            service_credential: HTTPAuthorizationCredentials | None = Security(
                service_credential_scheme
            ),
            actor_token: str | None = Security(actor_token_scheme),
            request_id: str | None = Header(default=None, alias="X-Request-Id"),
            trace_parent: str | None = Header(default=None, alias="traceparent"),
        ) -> InvocationIdentity:
            effective_request_id = request_id or f"req_{uuid4().hex}"
            if service_credential is None or service_credential.scheme != "Bearer":
                raise AuthenticationProblem(
                    "Bearer token is required", effective_request_id
                )
            if not actor_token:
                raise AuthenticationProblem(
                    "Actor token is required", effective_request_id
                )
            identity = identity_verifier.verify(
                service_token=service_credential.credentials,
                actor_token=actor_token,
                required_component=COMPONENT_CODE,
                required_scope=required_scope,
                request_id=effective_request_id,
            )
            return replace(
                identity,
                trace_parent=(
                    trace_parent
                    if trace_parent and TRACE_PARENT_PATTERN.fullmatch(trace_parent)
                    else None
                ),
            )

        return verify

    @app.post(
        "/api/v1/control-system/short-term-memory/turns:commit",
        operation_id="commitShortTermTurn",
    )
    async def commit_turn(
        request: CommitTurnRequest,
        background_tasks: BackgroundTasks,
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=16, max_length=128
        ),
        identity: InvocationIdentity = Depends(
            require_identity("component:short-term-memory:write")
        ),
    ) -> dict[str, object]:
        result = await memory.commit_turn(
            identity,
            ConversationTurn(
                turn_id=request.turn_id,
                user_message=request.user_message,
                assistant_message=request.assistant_message,
                occurred_at=request.occurred_at,
            ),
            idempotency_key,
        )
        if not result.duplicate:
            background_tasks.add_task(memory.refresh_summary_if_needed, identity)
        return {
            "data": {
                "turnId": result.turn_id,
                "duplicate": result.duplicate,
                "messageCount": result.message_count,
            },
            "meta": _meta(identity.request_id),
        }

    @app.post(
        "/api/v1/control-system/short-term-memory/context:prepare",
        operation_id="prepareShortTermContext",
    )
    async def prepare_context(
        request: PrepareContextRequest,
        identity: InvocationIdentity = Depends(
            require_identity("component:short-term-memory:read")
        ),
    ) -> dict[str, object]:
        prepared = await memory.prepare_context(
            identity,
            max_context_tokens=request.max_context_tokens,
        )
        data: dict[str, object] = {
            "messages": [
                {
                    "turnId": message.turn_id,
                    "role": message.role,
                    "content": message.content,
                    "occurredAt": message.occurred_at.isoformat(),
                }
                for message in prepared.messages
            ]
        }
        if prepared.summary is not None:
            data["summary"] = {
                "content": prepared.summary.summary,
                "throughTurnId": prepared.summary.through_turn_id,
                "model": prepared.summary.model,
                "updatedAt": prepared.summary.updated_at.isoformat(),
            }
        summary_meta = (
            {"summaryStatus": prepared.summary_status}
            if prepared.summary_status != "DISABLED"
            else {}
        )
        return {
            "data": data,
            "meta": {
                **_meta(identity.request_id),
                "estimatedTokens": True,
                "estimatedTokenCount": prepared.estimated_token_count,
                "trimmedMessageCount": prepared.trimmed_message_count,
                **summary_meta,
            },
        }

    @app.delete(
        "/api/v1/control-system/short-term-memory/sessions/{sessionId}",
        operation_id="clearShortTermSession",
    )
    async def clear_session(
        session_id: str = Path(alias="sessionId", min_length=1, max_length=128),
        identity: InvocationIdentity = Depends(
            require_identity("component:short-term-memory:delete")
        ),
    ) -> dict[str, object]:
        if identity.session_id != session_id:
            raise AuthorizationProblem(
                "Requested session does not match the Actor Token",
                identity.request_id,
            )
        cleared = await memory.clear_session(identity)
        return {
            "data": {"cleared": cleared},
            "meta": _meta(identity.request_id),
        }

    @app.get("/health/live", operation_id="controlSystemLive")
    async def live() -> dict[str, str]:
        return {"status": "UP"}

    @app.get("/health/ready", operation_id="controlSystemReady")
    async def ready() -> JSONResponse:
        store_ready = await session_store.health()
        degraded_dependencies: list[str] = []
        if summary_generator is not None:
            health = getattr(summary_generator, "health", None)
            if health is not None and not await health():
                degraded_dependencies.append("runtime-inference")
        content: dict[str, object] = {
            "status": "UP" if store_ready else "DOWN",
            "dependencies": {
                "shortTermStore": "UP" if store_ready else "DOWN"
            },
        }
        if degraded_dependencies:
            content["degradedDependencies"] = degraded_dependencies
        return JSONResponse(
            status_code=200 if store_ready else 503,
            content=content,
        )

    @app.get("/version", operation_id="controlSystemVersion")
    async def version() -> dict[str, str]:
        return {
            "service": "control-system-service",
            "version": "0.2.0",
            "interfaceVersion": INTERFACE_VERSION,
        }

    @app.get("/metrics", operation_id="controlSystemMetrics", include_in_schema=False)
    async def metrics_endpoint() -> PlainTextResponse:
        return PlainTextResponse(
            metric_registry.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app


def _meta(request_id: str) -> dict[str, object]:
    return {
        "requestId": request_id,
        "componentCode": COMPONENT_CODE,
        "implementationCode": IMPLEMENTATION_CODE,
        "interfaceVersion": INTERFACE_VERSION,
    }
