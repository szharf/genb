import json
from time import monotonic

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.responses import StreamingResponse

from .errors import RuntimeProblem
from .identity import CallerIdentity, IdentityVerifier
from .models import (
    EmbeddingRequest,
    EmbeddingResponse,
    InferenceRequest,
    InferenceResponse,
)
from .provider import FakeModelProvider, ModelProvider
from .protection import RuntimeCapacityGuard, RuntimeProtectionSettings
from .service import InferenceService
from .telemetry import MetricsRegistry

INFER_SCOPE = "component:inference-engine:infer"
EMBED_SCOPE = "component:inference-engine:embed"
MODELS_READ_SCOPE = "component:inference-engine:models:read"
HEALTH_READ_SCOPE = "component:inference-engine:health:read"


def create_app(
    *,
    identity_verifier: IdentityVerifier,
    provider: ModelProvider | None = None,
    environment: str = "local",
    protection_settings: RuntimeProtectionSettings | None = None,
    metrics: MetricsRegistry | None = None,
) -> FastAPI:
    app = FastAPI(title="GenB Runtime System", version="0.1.0")
    active_provider = provider or FakeModelProvider()
    service = InferenceService(active_provider)
    metric_registry = metrics or MetricsRegistry()
    capacity_guard = RuntimeCapacityGuard(
        protection_settings or RuntimeProtectionSettings(), metric_registry
    )
    app.state.metrics = metric_registry

    @app.middleware("http")
    async def measure_http(request: Request, call_next):
        started = monotonic()
        response = await call_next(request)
        route = request.scope.get("route")
        operation = getattr(route, "operation_id", None) or "unmatched"
        metric_registry.increment(
            "runtime_http_requests_total",
            {"operation": operation, "status": str(response.status_code)},
        )
        metric_registry.observe(
            "runtime_http_duration_seconds",
            monotonic() - started,
            {"operation": operation},
        )
        return response

    @app.exception_handler(RuntimeProblem)
    async def handle_runtime_problem(
        _request: Request, problem: RuntimeProblem
    ) -> JSONResponse:
        headers = None
        if problem.code == "MODEL_RATE_LIMITED":
            headers = {"Retry-After": str(capacity_guard.settings.window_seconds)}
        return JSONResponse(
            status_code=problem.status,
            headers=headers,
            media_type="application/problem+json",
            content={
                "type": f"https://errors.genb.local/{problem.code.lower().replace('_', '-')}",
                "title": problem.title,
                "status": problem.status,
                "detail": problem.detail,
                "code": problem.code,
                "requestId": problem.request_id,
                "retryable": problem.retryable,
            },
        )

    @app.exception_handler(HTTPException)
    async def handle_http_problem(
        request: Request, problem: HTTPException
    ) -> JSONResponse:
        if problem.status_code == status.HTTP_401_UNAUTHORIZED:
            code = "MODEL_CALLER_UNAUTHENTICATED"
            title = "Model caller is unauthenticated"
        elif problem.status_code == status.HTTP_403_FORBIDDEN:
            code = "MODEL_SCOPE_DENIED"
            title = "Model scope is denied"
        else:
            code = "MODEL_REQUEST_REJECTED"
            title = "Model request was rejected"
        request_id = request.headers.get("X-Request-Id", "unknown")
        return JSONResponse(
            status_code=problem.status_code,
            media_type="application/problem+json",
            content={
                "type": f"https://errors.genb.local/{code.lower().replace('_', '-')}",
                "title": title,
                "status": problem.status_code,
                "detail": str(problem.detail),
                "code": code,
                "requestId": request_id,
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
                "type": "https://errors.genb.local/model-request-invalid",
                "title": "Model request is invalid",
                "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "detail": "The request did not satisfy the Inference Interface.",
                "code": "MODEL_REQUEST_INVALID",
                "requestId": request_id,
                "retryable": False,
            },
        )

    def require_scope(required_scope: str):
        def verify_scope(
            authorization: str | None = Header(default=None),
        ) -> CallerIdentity:
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Bearer token is required",
                )
            identity = identity_verifier.verify(
                authorization.removeprefix("Bearer ")
            )
            if identity is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Bearer token is invalid",
                )
            if required_scope not in identity.scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required scope is missing: {required_scope}",
                )
            return identity

        return verify_scope

    require_inference_identity = require_scope(INFER_SCOPE)
    require_embedding_identity = require_scope(EMBED_SCOPE)
    require_models_identity = require_scope(MODELS_READ_SCOPE)
    require_health_identity = require_scope(HEALTH_READ_SCOPE)

    @app.post(
        "/api/v1/runtime-system/inference",
        response_model=InferenceResponse,
        response_model_by_alias=True,
    )
    async def infer(
        request: InferenceRequest,
        request_id: str = Header(alias="X-Request-Id"),
        identity: CallerIdentity = Depends(require_inference_identity),
    ) -> InferenceResponse:
        lease = await capacity_guard.acquire(
            identity,
            input_characters=_inference_characters(request),
            request_id=request_id,
        )
        async with lease:
            return await service.infer(request, request_id)

    @app.post("/api/v1/runtime-system/inference:stream")
    async def stream_inference(
        request: InferenceRequest,
        request_id: str = Header(alias="X-Request-Id"),
        identity: CallerIdentity = Depends(require_inference_identity),
    ) -> StreamingResponse:
        lease = await capacity_guard.acquire(
            identity,
            input_characters=_inference_characters(request),
            request_id=request_id,
        )

        async def event_stream():
            try:
                async for event_name, payload in service.stream_events(
                    request, request_id
                ):
                    data = json.dumps(
                        payload, ensure_ascii=False, separators=(",", ":")
                    )
                    yield f"event: {event_name}\ndata: {data}\n\n"
            finally:
                lease.release()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post(
        "/api/v1/runtime-system/embeddings",
        response_model=EmbeddingResponse,
        response_model_by_alias=True,
    )
    async def embed(
        request: EmbeddingRequest,
        request_id: str = Header(alias="X-Request-Id"),
        identity: CallerIdentity = Depends(require_embedding_identity),
    ) -> EmbeddingResponse:
        lease = await capacity_guard.acquire(
            identity,
            input_characters=sum(len(value) for value in request.inputs),
            request_id=request_id,
        )
        async with lease:
            return await service.embed(request, request_id)

    @app.get("/api/v1/runtime-system/models")
    async def models(
        _request_id: str = Header(alias="X-Request-Id"),
        _identity: CallerIdentity = Depends(require_models_identity),
    ) -> dict[str, object]:
        return {"data": active_provider.models()}

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "UP"}

    @app.get("/health/ready")
    async def ready() -> JSONResponse:
        provider_health = await active_provider.health()
        if environment == "production" and provider_health.provider == "FAKE":
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "DOWN",
                    "environment": environment,
                    "reason": "FAKE_PROVIDER_NOT_ALLOWED",
                },
            )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "UP",
                "environment": environment,
                "providers": [
                    {
                        "provider": provider_health.provider,
                        "status": provider_health.status,
                    }
                ],
            },
        )

    @app.get("/internal/health/models")
    async def model_health(
        request_id: str = Header(alias="X-Request-Id"),
        _identity: CallerIdentity = Depends(require_health_identity),
    ) -> dict[str, object]:
        provider_health = await active_provider.health()
        return {
            "data": [
                {
                    "provider": provider_health.provider,
                    "status": provider_health.status,
                }
            ],
            "meta": {
                "requestId": request_id,
                "degraded": provider_health.status != "UP",
            },
        }

    @app.get("/internal/metrics", include_in_schema=False)
    async def metrics_endpoint(
        _identity: CallerIdentity = Depends(require_health_identity),
    ) -> PlainTextResponse:
        return PlainTextResponse(
            metric_registry.render(), media_type="text/plain; version=0.0.4"
        )

    return app


def _inference_characters(request: InferenceRequest) -> int:
    total = sum(len(message.content) for message in request.messages)
    if request.response_format is not None:
        total += len(
            json.dumps(
                request.response_format.json_schema,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    return total
