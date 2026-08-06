from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "contracts"
CURRENT_COMPONENTS = {
    "SHORT_TERM_MEMORY": ROOT / "short-term-memory-service" / "component-manifest.json",
    "PLANNING_REASONING": ROOT / "planning-reasoning-service" / "component-manifest.json",
    "LONG_TERM_MEMORY": ROOT / "long-term-memory-service" / "component-manifest.json",
}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def test_current_component_services_publish_unique_valid_manifests() -> None:
    schema_path = CONTRACT_ROOT / "core-component-service-manifest.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = set(schema["required"])
    allowed_systems = set(schema["properties"]["systemCode"]["enum"])
    allowed_components = set(schema["properties"]["componentCode"]["enum"])

    implementation_codes: set[str] = set()
    for expected_component, path in CURRENT_COMPONENTS.items():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert required <= manifest.keys()
        assert manifest["manifestVersion"] == "1.0"
        assert manifest["systemCode"] in allowed_systems
        assert manifest["componentCode"] == expected_component
        assert manifest["componentCode"] in allowed_components
        assert manifest["runtimeType"] == "HTTP"
        assert manifest["implementationCode"] not in implementation_codes
        implementation_codes.add(manifest["implementationCode"])
        assert manifest["health"] == {
            "livePath": "/health/live",
            "readyPath": "/health/ready",
            "versionPath": "/version",
        }
        assert manifest["auth"]["type"] == "BEARER_JWT"
        assert manifest["auth"]["scopes"]
        assert all(scope.startswith("component:") for scope in manifest["auth"]["scopes"])
        openapi_path = path.parent / manifest["openApiPath"]
        assert openapi_path.is_file()
        openapi = json.loads(openapi_path.read_text(encoding="utf-8"))
        assert openapi["info"]["version"] == manifest["interfaceVersion"]
        operation_ids: set[str] = set()
        for path_item in openapi["paths"].values():
            for method, operation in path_item.items():
                if method.lower() in HTTP_METHODS:
                    assert operation.get("operationId")
                    assert operation["operationId"] not in operation_ids
                    operation_ids.add(operation["operationId"])
        assert (path.parent / manifest["configSchemaPath"]).is_file()


def test_genb_catalog_seed_uses_the_manifest_stable_codes() -> None:
    schema = json.loads(
        (CONTRACT_ROOT / "core-component-service-manifest.schema.json").read_text(encoding="utf-8")
    )
    initializer = (
        ROOT
        / "gen-b"
        / "gen-b-backend"
        / "src"
        / "main"
        / "java"
        / "com"
        / "genb"
        / "console"
        / "config"
        / "CoreComponentCatalogInitializer.java"
    ).read_text(encoding="utf-8")

    seeded_systems = set(re.findall(r'ensureSystem\("([A-Z_]+)"', initializer))
    seeded_components = set(re.findall(r'seed\([^,]+, "([A-Z_]+)"', initializer))

    assert seeded_systems == set(schema["properties"]["systemCode"]["enum"])
    assert seeded_components == set(schema["properties"]["componentCode"]["enum"])
