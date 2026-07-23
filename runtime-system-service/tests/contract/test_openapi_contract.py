import json
from pathlib import Path


def test_static_openapi_contract_contains_the_iteration_one_interfaces() -> None:
    contract_path = (
        Path(__file__).parents[2] / "openapi" / "runtime-inference-v1.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    assert contract["openapi"] == "3.1.0"
    assert set(contract["paths"]) == {
        "/inference",
        "/inference:stream",
        "/embeddings",
        "/models",
    }
    assert contract["components"]["securitySchemes"]["bearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
    }
