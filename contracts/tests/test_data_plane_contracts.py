from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "contracts"
SCHEMAS = {
    "data-plane-config-snapshot.schema.json",
    "gateway-identity-token-claims.schema.json",
    "capability-invocation.schema.json",
    "data-plane-adapter-descriptor.schema.json",
    "problem-details.schema.json",
}
OPENAPI_DOCUMENTS = {
    "genb-data-plane-gateway.openapi.json",
    "genb-data-plane-control.openapi.json",
}
FORBIDDEN_SNAPSHOT_FIELDS = {
    "secret",
    "secretValue",
    "apiKey",
    "actorToken",
    "portalToken",
    "sessionGrant",
}


def load_json(name: str) -> dict:
    return json.loads((CONTRACT_ROOT / name).read_text(encoding="utf-8"))


def property_names(value: object) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            names.update(properties)
        for child in value.values():
            names.update(property_names(child))
    elif isinstance(value, list):
        for child in value:
            names.update(property_names(child))
    return names


class DataPlaneContractTest(unittest.TestCase):
    def test_all_contract_documents_are_parseable_and_versioned(self) -> None:
        for name in SCHEMAS:
            schema = load_json(name)
            self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
            self.assertTrue(schema["$id"].startswith("https://genb.local/contracts/"))
            self.assertEqual("object", schema["type"])

        for name in OPENAPI_DOCUMENTS:
            document = load_json(name)
            self.assertEqual("3.1.0", document["openapi"])
            self.assertRegex(document["info"]["version"], r"^\d+\.\d+\.\d+$")

    def test_snapshot_uses_the_same_fourteen_stable_capability_codes(self) -> None:
        manifest = load_json("core-component-service-manifest.schema.json")
        snapshot = load_json("data-plane-config-snapshot.schema.json")
        expected = set(manifest["properties"]["componentCode"]["enum"])
        actual = set(snapshot["$defs"]["capabilityCode"]["enum"])
        self.assertEqual(expected, actual)
        self.assertEqual(14, len(actual))

    def test_snapshot_contains_references_but_no_secret_values(self) -> None:
        snapshot = load_json("data-plane-config-snapshot.schema.json")
        names = property_names(snapshot)
        self.assertIn("credentialRef", names)
        self.assertFalse(FORBIDDEN_SNAPSHOT_FIELDS & names)
        self.assertFalse(snapshot["additionalProperties"])

    def test_identity_claims_fix_a_short_lived_user_agent_session_context(self) -> None:
        claims = load_json("gateway-identity-token-claims.schema.json")
        required = set(claims["required"])
        self.assertEqual(
            {"iss", "sub", "aud", "iat", "exp", "jti", "tenantId", "userId", "agentId", "sessionId"},
            required,
        )
        self.assertFalse(claims["additionalProperties"])

    def test_public_interfaces_have_unique_operation_ids_and_resolvable_file_refs(self) -> None:
        operation_ids: set[str] = set()
        for name in OPENAPI_DOCUMENTS:
            document = load_json(name)
            for path_item in document["paths"].values():
                for method, operation in path_item.items():
                    if method not in {"get", "post", "put", "patch", "delete"}:
                        continue
                    operation_id = operation["operationId"]
                    self.assertNotIn(operation_id, operation_ids)
                    operation_ids.add(operation_id)
                    self._assert_refs_resolve(operation)

    def test_problem_details_has_stable_security_and_routing_errors(self) -> None:
        problem = load_json("problem-details.schema.json")
        self.assertEqual(
            {"type", "title", "status", "detail", "code", "requestId", "retriable"},
            set(problem["required"]),
        )
        codes = set(problem["properties"]["code"]["enum"])
        self.assertTrue(
            {"INVALID_IDENTITY_TOKEN", "ACCESS_DENIED", "CAPABILITY_NOT_BOUND", "IMPLEMENTATION_UNAVAILABLE", "OPERATION_NOT_FOUND"}
            <= codes
        )

    def test_control_write_interfaces_have_closed_versioned_request_schemas(self) -> None:
        control = load_json("genb-data-plane-control.openapi.json")
        expected_schemas = {
            "/api/v1/internal/data-plane/identity/exchange": "DataPlaneIdentityExchangeRequest",
            "/api/v1/internal/data-plane/identity/revoke": "DataPlaneIdentityRevokeRequest",
            "/api/v1/internal/data-plane/actor-token": "DataPlaneActorTokenRequest",
            "/api/v1/internal/data-plane/audits:batch": "DataPlaneAuditBatchRequest",
        }
        for path, schema_name in expected_schemas.items():
            schema = control["components"]["schemas"][schema_name]
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(
                f"#/components/schemas/{schema_name}",
                control["paths"][path]["post"]["requestBody"]["content"]
                ["application/json"]["schema"]["$ref"],
            )
            self.assertEqual({"1.0"}, set(schema["properties"]["schemaVersion"]["enum"]))

        audit_event = control["components"]["schemas"]["DataPlaneAuditEventRequest"]
        self.assertFalse(audit_event["additionalProperties"])
        self.assertFalse(FORBIDDEN_SNAPSHOT_FIELDS & set(audit_event["properties"]))

    def _assert_refs_resolve(self, value: object) -> None:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str) and not ref.startswith("#"):
                self.assertTrue((CONTRACT_ROOT / ref).is_file(), ref)
            for child in value.values():
                self._assert_refs_resolve(child)
        elif isinstance(value, list):
            for child in value:
                self._assert_refs_resolve(child)


if __name__ == "__main__":
    unittest.main()
