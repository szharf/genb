from collections.abc import Callable
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, Path, Request, Security, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from .errors import AuthenticationProblem, AuthorizationProblem, ControlSystemProblem
from .identity import IdentityVerifier, InvocationIdentity
from .short_term_memory.models import (
    CommitTurnRequest,
    ConversationTurn,
    PrepareContextRequest,
)
from .short_term_memory.service import ShortTermMemoryService
from .short_term_memory.store import SessionStore

COMPONENT_CODE = "SHORT_TERM_MEMORY"
IMPLEMENTATION_CODE = "control-memory-v1"
INTERFACE_VERSION = "1.0.0"


def create_app(
    *,
    identity_verifier: IdentityVerifier,
    session_store: SessionStore,
    ttl_seconds: int = 86400,
    max_turns: int = 50,
) -> FastAPI:
    app = FastAPI(title="GenB Control System", version="0.1.0")
    memory = ShortTermMemoryService(
        session_store,
        ttl_seconds=ttl_seconds,
        max_turns=max_turns,
    )
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
            return identity_verifier.verify(
                service_token=service_credential.credentials,
                actor_token=actor_token,
                required_component=COMPONENT_CODE,
                required_scope=required_scope,
                request_id=effective_request_id,
            )

        return verify

    @app.post(
        "/api/v1/control-system/short-term-memory/turns:commit",
        operation_id="commitShortTermTurn",
    )
    async def commit_turn(
        request: CommitTurnRequest,
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=16, max_length=128
        ),
        identity: InvocationIdentity = Depends(require_identity("short-term:write")),
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
        identity: InvocationIdentity = Depends(require_identity("short-term:read")),
    ) -> dict[str, object]:
        messages, trimmed_count, estimated_token_count = await memory.prepare_context(
            identity,
            max_context_tokens=request.max_context_tokens,
        )
        return {
            "data": {
                "messages": [
                    {
                        "turnId": message.turn_id,
                        "role": message.role,
                        "content": message.content,
                        "occurredAt": message.occurred_at.isoformat(),
                    }
                    for message in messages
                ]
            },
            "meta": {
                **_meta(identity.request_id),
                "estimatedTokens": True,
                "estimatedTokenCount": estimated_token_count,
                "trimmedMessageCount": trimmed_count,
            },
        }

    @app.delete(
        "/api/v1/control-system/short-term-memory/sessions/{sessionId}",
        operation_id="clearShortTermSession",
    )
    async def clear_session(
        session_id: str = Path(alias="sessionId", min_length=1, max_length=128),
        identity: InvocationIdentity = Depends(require_identity("short-term:delete")),
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
        return JSONResponse(
            status_code=200 if store_ready else 503,
            content={
                "status": "UP" if store_ready else "DOWN",
                "dependencies": {
                    "shortTermStore": "UP" if store_ready else "DOWN"
                },
            },
        )

    @app.get("/version", operation_id="controlSystemVersion")
    async def version() -> dict[str, str]:
        return {
            "service": "control-system-service",
            "version": "0.1.0",
            "interfaceVersion": INTERFACE_VERSION,
        }

    return app


def _meta(request_id: str) -> dict[str, object]:
    return {
        "requestId": request_id,
        "componentCode": COMPONENT_CODE,
        "implementationCode": IMPLEMENTATION_CODE,
        "interfaceVersion": INTERFACE_VERSION,
    }
