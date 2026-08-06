from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import json
from threading import RLock
from typing import Literal, Protocol
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, ConfigDict, Field

from .models import NonBlankText, ShortText


PlanScope = tuple[str, str, str]


class PlanStepRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: ShortText
    completion_criteria: NonBlankText = Field(alias="completionCriteria")


class PlanCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: ShortText = Field(alias="taskId")
    goal: NonBlankText
    steps: list[PlanStepRequest] = Field(min_length=1, max_length=50)
    max_replans: int = Field(default=2, alias="maxReplans", ge=0, le=5)


class PlanStep(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    step_id: str = Field(alias="stepId")
    order: int = Field(ge=1)
    title: str
    completion_criteria: str = Field(alias="completionCriteria")
    status: Literal["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELLED"]


class PlanObservationRequest(BaseModel):
    source: Literal["USER", "TOOL", "SYSTEM"]
    content: NonBlankText


class PlanObservation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    observation_id: str = Field(alias="observationId")
    source: Literal["USER", "TOOL", "SYSTEM"]
    content: str
    created_at: datetime = Field(alias="createdAt")


class PlanReplanRequest(BaseModel):
    reason: NonBlankText
    steps: list[PlanStepRequest] = Field(min_length=1, max_length=50)


class PlanCancelRequest(BaseModel):
    reason: NonBlankText


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    plan_id: str = Field(alias="planId")
    task_id: str = Field(alias="taskId")
    goal: str
    status: Literal["ACTIVE", "REPLAN_REQUIRED", "COMPLETED", "CANCELLED"]
    revision: int = Field(ge=1)
    steps: list[PlanStep]
    observations: list[PlanObservation] = Field(default_factory=list)
    replan_count: int = Field(alias="replanCount", ge=0)
    max_replans: int = Field(alias="maxReplans", ge=0)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ExecutionPlanResponse(BaseModel):
    data: ExecutionPlan


class StepTransitionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    target_status: Literal["IN_PROGRESS", "COMPLETED", "FAILED"] = Field(
        alias="targetStatus"
    )


PlanMutation = Callable[[ExecutionPlan | None], ExecutionPlan | None]


class PlanStore(Protocol):
    name: str

    def get(self, scope: PlanScope, plan_id: str) -> ExecutionPlan | None: ...

    def execute(
        self,
        scope: PlanScope,
        *,
        plan_id: str | None,
        operation: str,
        idempotency_key: str,
        fingerprint: str,
        mutation: PlanMutation,
    ) -> ExecutionPlan | None: ...

    def ready(self) -> bool: ...


class InMemoryPlanStore:
    name = "IN_MEMORY"

    def __init__(self) -> None:
        self._plans: dict[tuple[str, str, str, str], ExecutionPlan] = {}
        self._idempotency: dict[
            tuple[str, str, str, str, str], tuple[str, ExecutionPlan]
        ] = {}
        self._lock = RLock()

    def get(self, scope: PlanScope, plan_id: str) -> ExecutionPlan | None:
        with self._lock:
            plan = self._plans.get((*scope, plan_id))
            return plan.model_copy(deep=True) if plan is not None else None

    def execute(
        self,
        scope: PlanScope,
        *,
        plan_id: str | None,
        operation: str,
        idempotency_key: str,
        fingerprint: str,
        mutation: PlanMutation,
    ) -> ExecutionPlan | None:
        with self._lock:
            idempotency_scope = (*scope, operation, idempotency_key)
            replay = self._idempotency.get(idempotency_scope)
            if replay is not None:
                if replay[0] != fingerprint:
                    raise ValueError("IDEMPOTENCY_CONFLICT")
                return replay[1].model_copy(deep=True)
            current = self._plans.get((*scope, plan_id)) if plan_id else None
            result = mutation(
                current.model_copy(deep=True) if current is not None else None
            )
            if result is None:
                return None
            stored = result.model_copy(deep=True)
            self._plans[(*scope, stored.plan_id)] = stored
            self._idempotency[idempotency_scope] = (
                fingerprint,
                stored.model_copy(deep=True),
            )
            return stored.model_copy(deep=True)

    def ready(self) -> bool:
        return True


class PostgreSQLPlanStore:
    name = "POSTGRESQL"

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN is required")
        self._dsn = dsn

    def get(self, scope: PlanScope, plan_id: str) -> ExecutionPlan | None:
        with self._connection() as connection, connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT plan_json FROM planning_execution_plans
                WHERE tenant_id=%s AND agent_id=%s AND user_id=%s AND plan_id=%s
                """,
                (*scope, plan_id),
            )
            row = cursor.fetchone()
            return _plan_from_json(row["plan_json"]) if row else None

    def execute(
        self,
        scope: PlanScope,
        *,
        plan_id: str | None,
        operation: str,
        idempotency_key: str,
        fingerprint: str,
        mutation: PlanMutation,
    ) -> ExecutionPlan | None:
        with self._connection() as connection, connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            if plan_id is not None:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    ("plan|" + "|".join((*scope, plan_id)),),
                )
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                ("idem|" + "|".join((*scope, operation, idempotency_key)),),
            )
            cursor.execute(
                """
                SELECT request_fingerprint, response_json
                FROM planning_plan_idempotency
                WHERE tenant_id=%s AND agent_id=%s AND user_id=%s
                  AND operation=%s AND idempotency_key=%s
                FOR UPDATE
                """,
                (*scope, operation, idempotency_key),
            )
            replay = cursor.fetchone()
            if replay is not None:
                if replay["request_fingerprint"] != fingerprint:
                    raise ValueError("IDEMPOTENCY_CONFLICT")
                return _plan_from_json(replay["response_json"])

            current = None
            if plan_id is not None:
                cursor.execute(
                    """
                    SELECT plan_json FROM planning_execution_plans
                    WHERE tenant_id=%s AND agent_id=%s AND user_id=%s AND plan_id=%s
                    FOR UPDATE
                    """,
                    (*scope, plan_id),
                )
                row = cursor.fetchone()
                current = _plan_from_json(row["plan_json"]) if row else None
            result = mutation(current)
            if result is None:
                return None
            document = result.model_dump(mode="json", by_alias=True)
            cursor.execute(
                """
                INSERT INTO planning_execution_plans
                  (tenant_id, agent_id, user_id, plan_id, task_id, status,
                   revision, plan_json, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                ON CONFLICT (tenant_id, agent_id, user_id, plan_id)
                DO UPDATE SET task_id=EXCLUDED.task_id,
                              status=EXCLUDED.status,
                              revision=EXCLUDED.revision,
                              plan_json=EXCLUDED.plan_json,
                              updated_at=EXCLUDED.updated_at
                """,
                (
                    *scope,
                    result.plan_id,
                    result.task_id,
                    result.status,
                    result.revision,
                    json.dumps(document, ensure_ascii=False, separators=(",", ":")),
                    result.created_at,
                    result.updated_at,
                ),
            )
            cursor.execute(
                """
                INSERT INTO planning_plan_idempotency
                  (tenant_id, agent_id, user_id, operation, idempotency_key,
                   request_fingerprint, response_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
                """,
                (
                    *scope,
                    operation,
                    idempotency_key,
                    fingerprint,
                    json.dumps(document, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            return result.model_copy(deep=True)

    def ready(self) -> bool:
        try:
            with self._connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT to_regclass('planning_execution_plans') IS NOT NULL
                       AND to_regclass('planning_plan_idempotency') IS NOT NULL
                    """
                )
                return bool(cursor.fetchone()[0])
        except psycopg2.Error:
            return False

    @contextmanager
    def _connection(self) -> Iterator:
        connection = psycopg2.connect(self._dsn, connect_timeout=3)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class PlanLifecycle:
    """Owns the complete plan state machine behind a storage-independent Interface."""

    def __init__(self, store: PlanStore | None = None) -> None:
        self.store = store or InMemoryPlanStore()

    def create(
        self,
        request: PlanCreateRequest,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        idempotency_key: str,
    ) -> ExecutionPlan:
        scope = (tenant_id, agent_id, user_id)

        def create_plan(_current: ExecutionPlan | None) -> ExecutionPlan:
            now = datetime.now(UTC)
            return ExecutionPlan(
                planId=f"plan_{uuid4().hex}",
                taskId=request.task_id,
                goal=request.goal,
                status="ACTIVE",
                revision=1,
                steps=[
                    PlanStep(
                        stepId=f"step-{index}",
                        order=index,
                        title=step.title,
                        completionCriteria=step.completion_criteria,
                        status="PENDING",
                    )
                    for index, step in enumerate(request.steps, start=1)
                ],
                replanCount=0,
                maxReplans=request.max_replans,
                createdAt=now,
                updatedAt=now,
            )

        result = self.store.execute(
            scope,
            plan_id=None,
            operation="create",
            idempotency_key=idempotency_key,
            fingerprint=_fingerprint(request),
            mutation=create_plan,
        )
        assert result is not None
        return result

    def get(
        self,
        plan_id: str,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
    ) -> ExecutionPlan | None:
        return self.store.get((tenant_id, agent_id, user_id), plan_id)

    def transition_step(
        self,
        plan_id: str,
        step_id: str,
        request: StepTransitionRequest,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        idempotency_key: str,
    ) -> ExecutionPlan | None:
        def transition(plan: ExecutionPlan | None) -> ExecutionPlan | None:
            if plan is None:
                return None
            if plan.status in {"COMPLETED", "CANCELLED"}:
                raise ValueError("PLAN_TERMINAL")
            if plan.status != "ACTIVE":
                raise ValueError("PLAN_NOT_ACTIVE")
            step_index = next(
                (
                    index
                    for index, step in enumerate(plan.steps)
                    if step.step_id == step_id
                ),
                None,
            )
            if step_index is None:
                raise ValueError("STEP_NOT_FOUND")
            step = plan.steps[step_index]
            if request.target_status == "IN_PROGRESS":
                if step.status != "PENDING":
                    raise ValueError("INVALID_STEP_TRANSITION")
                if any(
                    previous.status != "COMPLETED"
                    for previous in plan.steps[:step_index]
                ):
                    raise ValueError("STEP_ORDER_VIOLATION")
                step.status = "IN_PROGRESS"
            elif request.target_status == "COMPLETED":
                if step.status != "IN_PROGRESS":
                    raise ValueError("INVALID_STEP_TRANSITION")
                step.status = "COMPLETED"
                if all(candidate.status == "COMPLETED" for candidate in plan.steps):
                    plan.status = "COMPLETED"
            elif request.target_status == "FAILED":
                if step.status != "IN_PROGRESS":
                    raise ValueError("INVALID_STEP_TRANSITION")
                step.status = "FAILED"
                plan.status = "REPLAN_REQUIRED"
            plan.updated_at = datetime.now(UTC)
            return plan

        return self._mutate(
            plan_id,
            f"transition:{plan_id}:{step_id}",
            request,
            transition,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            idempotency_key=idempotency_key,
        )

    def append_observation(
        self,
        plan_id: str,
        request: PlanObservationRequest,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        idempotency_key: str,
    ) -> ExecutionPlan | None:
        def append(plan: ExecutionPlan | None) -> ExecutionPlan | None:
            if plan is None:
                return None
            if plan.status not in {"ACTIVE", "REPLAN_REQUIRED"}:
                raise ValueError("PLAN_TERMINAL")
            now = datetime.now(UTC)
            plan.observations.append(
                PlanObservation(
                    observationId=f"obs_{uuid4().hex}",
                    source=request.source,
                    content=request.content,
                    createdAt=now,
                )
            )
            plan.updated_at = now
            return plan

        return self._mutate(
            plan_id,
            f"observation:{plan_id}",
            request,
            append,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            idempotency_key=idempotency_key,
        )

    def replan(
        self,
        plan_id: str,
        request: PlanReplanRequest,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        idempotency_key: str,
    ) -> ExecutionPlan | None:
        def apply(plan: ExecutionPlan | None) -> ExecutionPlan | None:
            if plan is None:
                return None
            if plan.status != "REPLAN_REQUIRED":
                raise ValueError("REPLAN_NOT_REQUIRED")
            if plan.replan_count >= plan.max_replans:
                raise ValueError("REPLAN_LIMIT_REACHED")
            plan.revision += 1
            plan.replan_count += 1
            completed = [step for step in plan.steps if step.status == "COMPLETED"]
            next_order = len(completed) + 1
            plan.steps = completed + [
                PlanStep(
                    stepId=f"step-r{plan.revision}-{index}",
                    order=next_order + index - 1,
                    title=step.title,
                    completionCriteria=step.completion_criteria,
                    status="PENDING",
                )
                for index, step in enumerate(request.steps, start=1)
            ]
            now = datetime.now(UTC)
            plan.observations.append(
                PlanObservation(
                    observationId=f"obs_{uuid4().hex}",
                    source="SYSTEM",
                    content=f"重规划原因：{request.reason}",
                    createdAt=now,
                )
            )
            plan.status = "ACTIVE"
            plan.updated_at = now
            return plan

        return self._mutate(
            plan_id,
            f"replan:{plan_id}",
            request,
            apply,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            idempotency_key=idempotency_key,
        )

    def cancel(
        self,
        plan_id: str,
        request: PlanCancelRequest,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        idempotency_key: str,
    ) -> ExecutionPlan | None:
        def apply(plan: ExecutionPlan | None) -> ExecutionPlan | None:
            if plan is None:
                return None
            if plan.status not in {"ACTIVE", "REPLAN_REQUIRED"}:
                raise ValueError("PLAN_TERMINAL")
            for step in plan.steps:
                if step.status != "COMPLETED":
                    step.status = "CANCELLED"
            now = datetime.now(UTC)
            plan.observations.append(
                PlanObservation(
                    observationId=f"obs_{uuid4().hex}",
                    source="SYSTEM",
                    content=f"取消原因：{request.reason}",
                    createdAt=now,
                )
            )
            plan.status = "CANCELLED"
            plan.updated_at = now
            return plan

        return self._mutate(
            plan_id,
            f"cancel:{plan_id}",
            request,
            apply,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            idempotency_key=idempotency_key,
        )

    def _mutate(
        self,
        plan_id: str,
        operation: str,
        request: BaseModel,
        mutation: PlanMutation,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        idempotency_key: str,
    ) -> ExecutionPlan | None:
        return self.store.execute(
            (tenant_id, agent_id, user_id),
            plan_id=plan_id,
            operation=operation,
            idempotency_key=idempotency_key,
            fingerprint=_fingerprint(request),
            mutation=mutation,
        )


def _plan_from_json(document: dict | str) -> ExecutionPlan:
    return (
        ExecutionPlan.model_validate_json(document)
        if isinstance(document, str)
        else ExecutionPlan.model_validate(document)
    )


def _fingerprint(request: BaseModel) -> str:
    return hashlib.sha256(
        json.dumps(
            request.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
