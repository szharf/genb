import json
from pathlib import Path

from fastapi.testclient import TestClient

from planning_reasoning.main import app


SERVICE_ROOT = Path(__file__).resolve().parents[1]


def test_version_identifies_the_public_component_implementation() -> None:
    with TestClient(app) as client:
        response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {
        "componentCode": "PLANNING_REASONING",
        "implementationCode": "planning-reasoning-service-v1",
        "interfaceVersion": "1.1.1",
        "serviceVersion": "0.1.0",
    }


def test_openapi_exposes_stable_planning_reasoning_operations() -> None:
    with TestClient(app) as client:
        document = client.get("/openapi.json").json()
        ready = client.get("/health/ready")

    assert document["openapi"] == "3.1.0"
    operation_ids = {
        operation["operationId"]
        for path in document["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "put", "delete"}
    }
    assert {
        "analyzePlanningRequirements",
        "conversePlanningRequirements",
        "createExecutionPlan",
        "getExecutionPlan",
        "transitionExecutionPlanStep",
        "appendExecutionPlanObservation",
        "replanExecutionPlan",
        "cancelExecutionPlan",
        "generateSkill",
        "validateSkill",
        "reviseSkill",
        "getSkillVersion",
    }.issubset(operation_ids)
    assert ready.status_code == 200
    assert ready.json()["status"] == "UP"
    assert ready.json()["authoring"] == "TEMPLATE"
    assert ready.json()["store"] in {"IN_MEMORY", "POSTGRESQL"}


def test_static_openapi_publishes_plan_lifecycle_interfaces() -> None:
    document = json.loads(
        (SERVICE_ROOT / "openapi" / "planning-reasoning-v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert {
        "/api/v1/planning-reasoning/plans",
        "/api/v1/planning-reasoning/plans/{plan_id}",
        "/api/v1/planning-reasoning/plans/{plan_id}/steps/{step_id}:transition",
        "/api/v1/planning-reasoning/plans/{plan_id}/observations",
        "/api/v1/planning-reasoning/plans/{plan_id}:replan",
        "/api/v1/planning-reasoning/plans/{plan_id}:cancel",
    } <= document["paths"].keys()
    assert set(document["paths"]) == set(app.openapi()["paths"])
