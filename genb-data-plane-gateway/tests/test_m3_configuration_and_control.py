from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from genb_gateway.capabilities import EnvironmentSecretResolver, PublishedCapabilityTable
from genb_gateway.control import ControlPlaneActorTokenProvider, HttpControlPlane
from genb_gateway.sessions import GatewaySession


class _Response:
    def __init__(self, value: dict) -> None:
        self._body = json.dumps(value).encode()
    def __enter__(self): return self
    def __exit__(self, *_args): return None
    def read(self): return self._body


class M3ConfigurationAndControlTest(unittest.TestCase):
    def test_snapshot_is_compiled_into_active_capability_without_secret_body(self) -> None:
        table = PublishedCapabilityTable.from_snapshot({
            "schemaVersion": "1.0", "configVersion": 7, "publishedAt": "2026-08-13T00:00:00Z",
            "agents": [],
            "implementations": [{
                "implementationCode": "memory-v1", "capabilityCode": "SHORT_TERM_MEMORY",
                "providerServiceName": "Memory Service", "adapterCode": "SHORT_TERM_MEMORY_HTTP",
                "adapterVersion": "1.0.0", "upstreamRef": "http://memory.internal:8701",
                "credentialRef": "env://MEMORY_SERVICE_TOKEN", "isolationMode": "SUBJECT_KEYS",
                "status": "PUBLISHED", "operations": [{
                    "operationId": "commitShortTermTurn", "timeoutMs": 1500,
                    "idempotency": "REQUIRED_KEY", "responseMode": "JSON", "maxRequestBytes": 8192,
                }],
            }],
            "bindings": [{
                "agentId": "agent-a", "capabilityCode": "SHORT_TERM_MEMORY",
                "implementationCode": "memory-v1", "bindingVersion": 3, "status": "ACTIVE",
            }],
        })
        binding = table.resolve("agent-a", "SHORT_TERM_MEMORY")
        self.assertEqual("SHORT_TERM_MEMORY_HTTP", binding.adapter_code)
        self.assertEqual("env://MEMORY_SERVICE_TOKEN", binding.credential_ref)
        self.assertEqual(1500, binding.operation("commitShortTermTurn").timeout_ms)
        self.assertFalse(hasattr(binding, "credential"))

    def test_secret_resolver_only_reads_explicit_environment_or_mounted_alias(self) -> None:
        with TemporaryDirectory() as directory:
            secret_file = Path(directory) / "planning-token"
            secret_file.write_text("file-secret\n", encoding="utf-8")
            resolver = EnvironmentSecretResolver(
                environ={"MEMORY_TOKEN": "env-secret", "PLANNING_TOKEN_FILE":str(secret_file)},
                mounted_files={"planning": secret_file},
            )
            self.assertEqual("env-secret", resolver.resolve("env://MEMORY_TOKEN"))
            self.assertEqual("file-secret", resolver.resolve("env://PLANNING_TOKEN"))
            self.assertEqual("file-secret", resolver.resolve("file://planning"))
            for reference in ("file://../planning-token", "file:///etc/passwd", "env://MISSING", "https://secret"):
                with self.assertRaises(LookupError): resolver.resolve(reference)

    def test_secret_resolver_maps_control_plane_alias_to_explicit_prefix(self) -> None:
        resolver = EnvironmentSecretResolver(environ={
            "GENB_SECRET_CORE_COMPONENTS_RUNTIME": "runtime-secret",
        })
        self.assertEqual(
            "runtime-secret",
            resolver.resolve("secret://core-components/runtime"),
        )
        with self.assertRaises(LookupError):
            resolver.resolve("secret://core-components/missing")

    def test_actor_token_provider_uses_session_grant_and_gateway_machine_identity(self) -> None:
        seen = {}
        def fake_urlopen(request, timeout):
            seen["url"], seen["authorization"] = request.full_url, request.headers["Authorization"]
            seen["body"] = json.loads(request.data)
            return _Response({
                "schemaVersion": "1.0", "actorToken": "signed-actor-token", "expiresAt": "2026-08-13T00:05:00Z",
                "capabilityCode": "SHORT_TERM_MEMORY", "implementationCode": "memory-v1", "bindingVersion": 3,
            })
        session = GatewaySession("session-a", "tenant-1", "user-a", "alice", "agent-a", "g" * 40,
                                 datetime(2026, 8, 13, 1, tzinfo=timezone.utc))
        with patch("genb_gateway.control.urlopen", fake_urlopen):
            token = ControlPlaneActorTokenProvider(
                HttpControlPlane("http://genb.local", "gateway-machine-token")
            ).issue(session, "SHORT_TERM_MEMORY")
        self.assertEqual("signed-actor-token", token)
        self.assertEqual("http://genb.local/api/v1/internal/data-plane/actor-token", seen["url"])
        self.assertEqual("Bearer gateway-machine-token", seen["authorization"])
        self.assertEqual({
            "schemaVersion": "1.0", "sessionGrant": "g" * 40, "agentId": "agent-a",
            "sessionId": "session-a", "capabilityCode": "SHORT_TERM_MEMORY",
        }, seen["body"])


if __name__ == "__main__": unittest.main()
