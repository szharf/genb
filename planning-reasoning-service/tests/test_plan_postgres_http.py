import os
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from planning_reasoning import main as main_module
from planning_reasoning import plan_lifecycle as lifecycle_module


def test_plan_survives_a_new_service_instance_with_postgres(monkeypatch) -> None:
    dsn = os.getenv("PLANNING_REASONING_POSTGRES_DSN")
    if not dsn:
        pytest.skip("PLANNING_REASONING_POSTGRES_DSN is not configured")
    suffix = uuid4().hex[:12]
    headers = {
        "X-Tenant-Id": f"tenant-plan-{suffix}",
        "X-Agent-Id": f"agent-plan-{suffix}",
        "X-User-Id": f"user-plan-{suffix}",
        "Idempotency-Key": f"idem-plan-{suffix}",
    }
    store_type = lifecycle_module.PostgreSQLPlanStore
    monkeypatch.setattr(
        main_module,
        "plan_lifecycle",
        lifecycle_module.PlanLifecycle(store_type(dsn)),
    )

    with TestClient(main_module.app) as client:
        created = client.post(
            "/api/v1/planning-reasoning/plans",
            headers=headers,
            json={
                "taskId": f"task-{suffix}",
                "goal": "验证计划跨实例恢复",
                "steps": [
                    {"title": "保存计划", "completionCriteria": "新实例可以读取"}
                ],
            },
        )
        assert created.status_code == 201
        plan = created.json()["data"]

        monkeypatch.setattr(
            main_module,
            "plan_lifecycle",
            lifecycle_module.PlanLifecycle(store_type(dsn)),
        )
        restored = client.get(
            f"/api/v1/planning-reasoning/plans/{plan['planId']}",
            headers=headers,
        )

    assert restored.status_code == 200
    assert restored.json()["data"] == plan


def test_create_plan_idempotency_survives_a_new_service_instance(monkeypatch) -> None:
    dsn = os.getenv("PLANNING_REASONING_POSTGRES_DSN")
    if not dsn:
        pytest.skip("PLANNING_REASONING_POSTGRES_DSN is not configured")
    suffix = uuid4().hex[:12]
    headers = {
        "X-Tenant-Id": f"tenant-idem-{suffix}",
        "X-Agent-Id": f"agent-idem-{suffix}",
        "X-User-Id": f"user-idem-{suffix}",
        "Idempotency-Key": f"idem-create-{suffix}",
    }
    payload = {
        "taskId": f"task-idem-{suffix}",
        "goal": "验证跨实例创建幂等",
        "steps": [{"title": "只创建一次", "completionCriteria": "响应完全一致"}],
    }
    store_type = lifecycle_module.PostgreSQLPlanStore
    monkeypatch.setattr(
        main_module,
        "plan_lifecycle",
        lifecycle_module.PlanLifecycle(store_type(dsn)),
    )

    with TestClient(main_module.app) as client:
        first = client.post(
            "/api/v1/planning-reasoning/plans",
            headers=headers,
            json=payload,
        )
        monkeypatch.setattr(
            main_module,
            "plan_lifecycle",
            lifecycle_module.PlanLifecycle(store_type(dsn)),
        )
        replayed = client.post(
            "/api/v1/planning-reasoning/plans",
            headers=headers,
            json=payload,
        )

    assert first.status_code == 201
    assert replayed.status_code == 201
    assert replayed.json() == first.json()


def test_postgres_plan_schema_has_no_physical_foreign_keys() -> None:
    dsn = os.getenv("PLANNING_REASONING_POSTGRES_DSN")
    if not dsn:
        pytest.skip("PLANNING_REASONING_POSTGRES_DSN is not configured")
    import psycopg2

    with psycopg2.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT count(*) FROM information_schema.table_constraints
            WHERE table_schema=current_schema()
              AND table_name=ANY(%s) AND constraint_type='FOREIGN KEY'
            """,
            (["planning_execution_plans", "planning_plan_idempotency"],),
        )
        foreign_key_count = cursor.fetchone()[0]

    assert foreign_key_count == 0
