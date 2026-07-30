import os
from typing import Annotated
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException

from .models import (
    RequirementAnalysisResponse,
    RequirementRequest,
    SkillArtifactResponse,
    SkillGenerateRequest,
    SkillReviseRequest,
    SkillValidationRequest,
    SkillValidationResponse,
)
from .service import (
    RequirementAnalyzer,
    RequirementClarificationRequired,
    SkillAuthoringService,
    TemplateSkillDraftWriter,
    SkillValidator,
)
from .inference import ModelAuthoringError, RuntimeInferenceSkillDraftWriter
from .repository import InMemorySkillRepository, PostgreSQLSkillRepository, SkillRepository
from .identity import (
    DevelopmentHeaderIdentityVerifier,
    GenBIdentityVerifier,
    IdentityProblem,
    InvocationIdentity,
)


app = FastAPI(
    title="GenB Planning and Reasoning Service",
    version="1.0.0",
    openapi_version="3.1.0",
)
analyzer = RequirementAnalyzer()
validator = SkillValidator()
repository: SkillRepository = (
    PostgreSQLSkillRepository(os.environ["PLANNING_REASONING_POSTGRES_DSN"])
    if os.getenv("PLANNING_REASONING_POSTGRES_DSN")
    else InMemorySkillRepository()
)
inference_url = os.getenv("PLANNING_REASONING_INFERENCE_URL", "").rstrip("/")
inference_client = httpx.Client(base_url=inference_url, timeout=60.0) if inference_url else None
draft_writer = (
    RuntimeInferenceSkillDraftWriter(
        client=inference_client,
        model_alias=os.getenv("PLANNING_REASONING_MODEL_ALIAS", "planning-authoring-default"),
    )
    if inference_client is not None
    else TemplateSkillDraftWriter()
)
authoring_mode = "MODEL" if inference_client is not None else "TEMPLATE"
authoring = SkillAuthoringService(analyzer, validator, repository, draft_writer)
if inference_client is not None:
    app.router.add_event_handler("shutdown", inference_client.close)


def configured_identity_verifier() -> DevelopmentHeaderIdentityVerifier | GenBIdentityVerifier:
    mode = os.getenv("PLANNING_REASONING_AUTH_MODE", "development_headers").lower()
    if mode == "development_headers":
        return DevelopmentHeaderIdentityVerifier()
    if mode != "genb":
        raise RuntimeError("PLANNING_REASONING_AUTH_MODE must be development_headers or genb")
    genb_url = os.getenv("PLANNING_REASONING_GENB_URL", "http://127.0.0.1:8581/api").rstrip("/")
    return GenBIdentityVerifier(
        client=httpx.Client(timeout=2.0),
        jwks_url=f"{genb_url}/.well-known/jwks.json",
        introspection_url=f"{genb_url}/v1/internal/service-credentials:introspect",
        internal_token=os.getenv("PLANNING_REASONING_GENB_INTERNAL_TOKEN", ""),
        issuer=os.getenv("PLANNING_REASONING_ACTOR_ISSUER", "genb"),
        audience=os.getenv("PLANNING_REASONING_ACTOR_AUDIENCE", "control-system"),
    )


identity_verifier = configured_identity_verifier()


def invocation_identity(
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
                tenant_id=tenant_id, agent_id=agent_id, user_id=user_id
            )
        service_token = (
            authorization.removeprefix("Bearer ")
            if authorization.startswith("Bearer ")
            else ""
        )
        return identity_verifier.verify(
            service_token=service_token,
            actor_token=actor_token,
            required_component="PLANNING_REASONING",
            required_scope="component:planning-reasoning:invoke",
            request_id=request_id,
        )
    except PermissionError as error:
        raise HTTPException(status_code=401, detail="调用身份无效") from error
    except IdentityProblem as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/health/ready", tags=["health"])
def ready() -> dict[str, str]:
    if not repository.ready():
        raise HTTPException(status_code=503, detail="Skill版本存储不可用")
    return {
        "status": "UP",
        "authoring": authoring_mode,
        "store": "POSTGRESQL" if isinstance(repository, PostgreSQLSkillRepository) else "IN_MEMORY",
    }


@app.post(
    "/api/v1/planning-reasoning/requirements:analyze",
    response_model=RequirementAnalysisResponse,
    tags=["requirements"],
    operation_id="analyzePlanningRequirements",
)
def analyze_requirements(
    request: RequirementRequest,
    _identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
) -> RequirementAnalysisResponse:
    return RequirementAnalysisResponse(data=analyzer.analyze(request))


@app.post(
    "/api/v1/planning-reasoning/skills:generate",
    response_model=SkillArtifactResponse,
    status_code=201,
    tags=["skill-authoring"],
    operation_id="generateSkill",
)
def generate_skill(
    request: SkillGenerateRequest,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    authorization: Annotated[str, Header(alias="Authorization")] = "",
    request_id: Annotated[str, Header(alias="X-Request-Id")] = "",
) -> SkillArtifactResponse:
    try:
        artifact = authoring.generate(
            request,
            tenant_id=identity.tenant_id,
            agent_id=identity.agent_id,
            idempotency_key=idempotency_key,
            service_token=_service_token(authorization),
            request_id=request_id or f"req_{uuid4().hex}",
        )
    except RequirementClarificationRequired as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "REQUIREMENT_CLARIFICATION_REQUIRED",
                "analysis": error.analysis.model_dump(by_alias=True),
            },
        ) from error
    except ValueError as error:
        if str(error) == "IDEMPOTENCY_CONFLICT":
            raise HTTPException(status_code=409, detail="幂等键对应的请求内容不一致") from error
        raise
    except ModelAuthoringError as error:
        raise HTTPException(status_code=502, detail="规划模型生成失败") from error
    return SkillArtifactResponse(data=artifact)


@app.post(
    "/api/v1/planning-reasoning/skills:validate",
    response_model=SkillValidationResponse,
    tags=["skill-authoring"],
    operation_id="validateSkill",
)
def validate_skill(
    request: SkillValidationRequest,
    _identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
) -> SkillValidationResponse:
    return SkillValidationResponse(
        data=validator.validate(request.skill_markdown, require_mcp=request.require_mcp)
    )


@app.post(
    "/api/v1/planning-reasoning/skills/{skill_id}:revise",
    response_model=SkillArtifactResponse,
    status_code=201,
    tags=["skill-authoring"],
    operation_id="reviseSkill",
)
def revise_skill(
    skill_id: str,
    request: SkillReviseRequest,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    authorization: Annotated[str, Header(alias="Authorization")] = "",
    request_id: Annotated[str, Header(alias="X-Request-Id")] = "",
) -> SkillArtifactResponse:
    try:
        artifact = authoring.revise(
            skill_id,
            request,
            tenant_id=identity.tenant_id,
            agent_id=identity.agent_id,
            idempotency_key=idempotency_key,
            service_token=_service_token(authorization),
            request_id=request_id or f"req_{uuid4().hex}",
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Skill或基础版本不存在") from error
    except ValueError as error:
        if str(error) == "STALE_BASE_VERSION":
            raise HTTPException(status_code=409, detail="基础版本不是当前最新版本") from error
        if str(error) == "IDEMPOTENCY_CONFLICT":
            raise HTTPException(status_code=409, detail="幂等键对应的请求内容不一致") from error
        raise
    except ModelAuthoringError as error:
        raise HTTPException(status_code=502, detail="规划模型修订失败") from error
    return SkillArtifactResponse(data=artifact)


def _service_token(authorization: str) -> str:
    return authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""


@app.get(
    "/api/v1/planning-reasoning/skills/{skill_id}/versions/{version}",
    response_model=SkillArtifactResponse,
    tags=["skill-authoring"],
    operation_id="getSkillVersion",
)
def get_skill_version(
    skill_id: str,
    version: int,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
) -> SkillArtifactResponse:
    artifact = authoring.get(
        skill_id, version, tenant_id=identity.tenant_id, agent_id=identity.agent_id
    )
    if artifact is None:
        raise HTTPException(status_code=404, detail="Skill版本不存在")
    return SkillArtifactResponse(data=artifact)
