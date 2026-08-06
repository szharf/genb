import os
import logging
from typing import Annotated
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException

from .models import (
    RequirementAnalysisResponse,
    RequirementConversationRequest,
    RequirementConversationResponse,
    RequirementRequest,
    SkillArtifactResponse,
    SkillGenerateRequest,
    SkillReviseRequest,
    SkillValidationRequest,
    SkillValidationResponse,
)
from .service import (
    RequirementAnalyzer,
    RequirementConversationService,
    RequirementClarificationRequired,
    SkillAuthoringService,
    TemplateSkillDraftWriter,
    SkillValidator,
)
from .inference import (
    ModelAuthoringError,
    RuntimeInferenceRequirementAnalyst,
    RuntimeInferenceSkillDraftWriter,
)
from .knowledge import ApprovedPlanningKnowledge
from .plan_lifecycle import (
    ExecutionPlanResponse,
    InMemoryPlanStore,
    PlanCancelRequest,
    PlanObservationRequest,
    PlanReplanRequest,
    PlanCreateRequest,
    PlanLifecycle,
    PostgreSQLPlanStore,
    StepTransitionRequest,
)
from .repository import (
    InMemoryRequirementDraftRepository,
    InMemorySkillRepository,
    PostgreSQLRequirementDraftRepository,
    PostgreSQLSkillRepository,
    SkillRepository,
)
from .identity import (
    DevelopmentHeaderIdentityVerifier,
    GenBIdentityVerifier,
    IdentityProblem,
    InvocationIdentity,
)


app = FastAPI(
    title="GenB Planning and Reasoning Service",
    version="1.1.1",
    openapi_version="3.1.0",
)
logger = logging.getLogger("planning_reasoning")
analyzer = RequirementAnalyzer()
validator = SkillValidator()
postgres_dsn = os.getenv("PLANNING_REASONING_POSTGRES_DSN", "")
repository: SkillRepository = (
    PostgreSQLSkillRepository(postgres_dsn)
    if postgres_dsn
    else InMemorySkillRepository()
)
requirement_repository = (
    PostgreSQLRequirementDraftRepository(postgres_dsn)
    if postgres_dsn
    else InMemoryRequirementDraftRepository()
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
requirement_conversation = (
    RequirementConversationService(
        repository=requirement_repository,
        analyst=RuntimeInferenceRequirementAnalyst(
            client=inference_client,
            model_alias=os.getenv("PLANNING_REASONING_ANALYSIS_MODEL_ALIAS", "planning-analysis-default"),
        ),
        knowledge=ApprovedPlanningKnowledge(),
    )
    if inference_client is not None
    else None
)
plan_store = (
    PostgreSQLPlanStore(postgres_dsn)
    if postgres_dsn
    else InMemoryPlanStore()
)
plan_lifecycle = PlanLifecycle(plan_store)
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
    if not repository.ready() or not plan_lifecycle.store.ready():
        raise HTTPException(status_code=503, detail="规划与推理存储不可用")
    return {
        "status": "UP",
        "authoring": authoring_mode,
        "store": "POSTGRESQL" if isinstance(repository, PostgreSQLSkillRepository) else "IN_MEMORY",
        "planStore": plan_lifecycle.store.name,
    }


@app.get("/version", tags=["health"], operation_id="getPlanningReasoningVersion")
def version() -> dict[str, str]:
    return {
        "componentCode": "PLANNING_REASONING",
        "implementationCode": "planning-reasoning-service-v1",
        "interfaceVersion": "1.1.1",
        "serviceVersion": "0.1.0",
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
    "/api/v1/planning-reasoning/requirements:converse",
    response_model=RequirementConversationResponse,
    tags=["requirements"],
    operation_id="conversePlanningRequirements",
)
def converse_requirements(
    request: RequirementConversationRequest,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
    authorization: Annotated[str, Header(alias="Authorization")] = "",
    request_id: Annotated[str, Header(alias="X-Request-Id")] = "",
) -> RequirementConversationResponse:
    if requirement_conversation is None:
        raise HTTPException(status_code=503, detail="规划需求分析模型未配置")
    try:
        result = requirement_conversation.converse(
            task_id=request.task_id,
            session_id=request.session_id,
            message=request.message,
            tenant_id=identity.tenant_id,
            agent_id=identity.agent_id,
            user_id=identity.user_id,
            service_token=_service_token(authorization),
            request_id=request_id or f"req_{uuid4().hex}",
        )
    except (ModelAuthoringError, ValueError) as error:
        logger.warning("requirement conversation failed: %s", error)
        raise HTTPException(status_code=502, detail="规划需求分析失败") from error
    return RequirementConversationResponse(data=result)


@app.post(
    "/api/v1/planning-reasoning/plans",
    response_model=ExecutionPlanResponse,
    status_code=201,
    tags=["plan-lifecycle"],
    operation_id="createExecutionPlan",
)
def create_plan(
    request: PlanCreateRequest,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
) -> ExecutionPlanResponse:
    try:
        plan = plan_lifecycle.create(
            request,
            tenant_id=identity.tenant_id,
            agent_id=identity.agent_id,
            user_id=identity.user_id,
            idempotency_key=idempotency_key,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return ExecutionPlanResponse(data=plan)


@app.get(
    "/api/v1/planning-reasoning/plans/{plan_id}",
    response_model=ExecutionPlanResponse,
    tags=["plan-lifecycle"],
    operation_id="getExecutionPlan",
)
def get_plan(
    plan_id: str,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
) -> ExecutionPlanResponse:
    plan = plan_lifecycle.get(
        plan_id,
        tenant_id=identity.tenant_id,
        agent_id=identity.agent_id,
        user_id=identity.user_id,
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="执行计划不存在")
    return ExecutionPlanResponse(data=plan)


@app.post(
    "/api/v1/planning-reasoning/plans/{plan_id}/steps/{step_id}:transition",
    response_model=ExecutionPlanResponse,
    tags=["plan-lifecycle"],
    operation_id="transitionExecutionPlanStep",
)
def transition_plan_step(
    plan_id: str,
    step_id: str,
    request: StepTransitionRequest,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
) -> ExecutionPlanResponse:
    try:
        plan = plan_lifecycle.transition_step(
            plan_id,
            step_id,
            request,
            tenant_id=identity.tenant_id,
            agent_id=identity.agent_id,
            user_id=identity.user_id,
            idempotency_key=idempotency_key,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if plan is None:
        raise HTTPException(status_code=404, detail="执行计划不存在")
    return ExecutionPlanResponse(data=plan)


@app.post(
    "/api/v1/planning-reasoning/plans/{plan_id}/observations",
    response_model=ExecutionPlanResponse,
    tags=["plan-lifecycle"],
    operation_id="appendExecutionPlanObservation",
)
def append_plan_observation(
    plan_id: str,
    request: PlanObservationRequest,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
) -> ExecutionPlanResponse:
    try:
        plan = plan_lifecycle.append_observation(
            plan_id,
            request,
            tenant_id=identity.tenant_id,
            agent_id=identity.agent_id,
            user_id=identity.user_id,
            idempotency_key=idempotency_key,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if plan is None:
        raise HTTPException(status_code=404, detail="执行计划不存在")
    return ExecutionPlanResponse(data=plan)


@app.post(
    "/api/v1/planning-reasoning/plans/{plan_id}:replan",
    response_model=ExecutionPlanResponse,
    tags=["plan-lifecycle"],
    operation_id="replanExecutionPlan",
)
def replan_execution_plan(
    plan_id: str,
    request: PlanReplanRequest,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
) -> ExecutionPlanResponse:
    try:
        plan = plan_lifecycle.replan(
            plan_id,
            request,
            tenant_id=identity.tenant_id,
            agent_id=identity.agent_id,
            user_id=identity.user_id,
            idempotency_key=idempotency_key,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if plan is None:
        raise HTTPException(status_code=404, detail="执行计划不存在")
    return ExecutionPlanResponse(data=plan)


@app.post(
    "/api/v1/planning-reasoning/plans/{plan_id}:cancel",
    response_model=ExecutionPlanResponse,
    tags=["plan-lifecycle"],
    operation_id="cancelExecutionPlan",
)
def cancel_execution_plan(
    plan_id: str,
    request: PlanCancelRequest,
    identity: Annotated[InvocationIdentity, Depends(invocation_identity)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
) -> ExecutionPlanResponse:
    try:
        plan = plan_lifecycle.cancel(
            plan_id,
            request,
            tenant_id=identity.tenant_id,
            agent_id=identity.agent_id,
            user_id=identity.user_id,
            idempotency_key=idempotency_key,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if plan is None:
        raise HTTPException(status_code=404, detail="执行计划不存在")
    return ExecutionPlanResponse(data=plan)


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
    InMemoryPlanStore,
