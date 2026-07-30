from fastapi.testclient import TestClient

from planning_reasoning.main import app


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
        "generateSkill",
        "validateSkill",
        "reviseSkill",
        "getSkillVersion",
    }.issubset(operation_ids)
    assert ready.status_code == 200
    assert ready.json()["status"] == "UP"
    assert ready.json()["authoring"] == "TEMPLATE"
    assert ready.json()["store"] in {"IN_MEMORY", "POSTGRESQL"}
