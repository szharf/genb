import json
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]


def test_manifest_and_openapi_publish_the_current_public_contract() -> None:
    manifest = json.loads((SERVICE_ROOT / "component-manifest.json").read_text("utf-8"))
    openapi = json.loads(
        (SERVICE_ROOT / "openapi" / "long-term-memory-v1.json").read_text("utf-8")
    )

    assert manifest["auth"]["scopes"] == [
        "component:long-term-memory:read",
        "component:long-term-memory:write",
        "component:long-term-memory:delete",
    ]
    assert set(openapi["paths"]) >= {
        "/api/v1/long-term-memory/extractions",
        "/api/v1/long-term-memory/extractions/{extraction_id}",
        "/api/v1/long-term-memory/memories:search",
        "/api/v1/long-term-memory/memories/{memory_id}",
        "/api/v1/long-term-memory/memories/{memory_id}:correct",
        "/api/v1/long-term-memory/memories/{memory_id}:feedback",
    }
    assert set(openapi["paths"]["/api/v1/long-term-memory/memories/{memory_id}"]) == {
        "delete"
    }
