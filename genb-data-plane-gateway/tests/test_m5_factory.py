from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import unittest

from genb_gateway.factory import build_gateway


SNAPSHOT = {
    "schemaVersion":"1.0", "configVersion":7, "publishedAt":"2026-08-13T13:00:00Z",
    "agents":[{"agentId":"agent-a", "status":"PUBLISHED", "upstreamRef":"http://agent.internal:18714",
               "identityMode":"SIGNED_TOKEN"}],
    "implementations":[{
        "implementationCode":"memory-v1", "capabilityCode":"SHORT_TERM_MEMORY", "providerServiceName":"Memory",
        "adapterCode":"SHORT_TERM_MEMORY_HTTP", "adapterVersion":"1.0.0",
        "upstreamRef":"http://memory.internal:8701", "credentialRef":"env://MEMORY_TOKEN",
        "isolationMode":"SUBJECT_KEYS", "status":"PUBLISHED", "operations":[{
            "operationId":"prepareShortTermContext", "timeoutMs":1000, "idempotency":"READ",
            "responseMode":"JSON", "maxRequestBytes":4096,
        }],
    }],
    "bindings":[{"agentId":"agent-a", "capabilityCode":"SHORT_TERM_MEMORY",
                 "implementationCode":"memory-v1", "bindingVersion":7, "status":"ACTIVE"}],
}


class Control:
    def get_version(self): return 7
    def get_snapshot(self): return SNAPSHOT
    def append_audits(self, events): return len(events)
    def issue_actor_token_lease(self, session, capability): raise AssertionError("not invoked during wiring")


class Redis:
    def __init__(self): self.values = {}
    def command(self, command, *parts):
        if command == "SET": self.values[parts[0]] = parts[1]; return "OK"
        if command == "GET": return self.values.get(parts[0])
        raise AssertionError((command, parts))


def get(app, path):
    sent = []
    async def receive(): return {"type":"http.disconnect"}
    async def send(message): sent.append(message)
    asyncio.run(app({
        "type":"http", "asgi":{"version":"3.0"}, "http_version":"1.1", "method":"GET",
        "scheme":"http", "path":path, "raw_path":path.encode(), "query_string":b"", "headers":[],
        "server":("gateway.local",80), "client":("127.0.0.1",12345),
    }, receive, send))
    start = next(item for item in sent if item["type"] == "http.response.start")
    return start["status"]


class M5FactoryTest(unittest.TestCase):
    def test_required_environment_is_closed_and_missing_values_fail_startup(self):
        with self.assertRaisesRegex(ValueError, "GENB_CONTROL_URL"):
            build_gateway({}, control_plane=Control(), redis=Redis())

    def test_complete_environment_builds_one_runtime_from_the_published_snapshot(self):
        environment = {
            "GENB_CONTROL_URL":"http://genb.internal:8581", "GENB_GATEWAY_MACHINE_TOKEN":"machine-token-value",
            "GENB_PUBLIC_ORIGIN":"https://agents.example.test", "GENB_PORTAL_AUTHORIZE_URL":"https://portal.example.test/authorize",
            "GENB_GATEWAY_CALLBACK_URL":"https://agents.example.test/agents/_auth/callback",
            "GENB_NGINX_TOKEN":"nginx-token-value", "GENB_INVALIDATION_TOKEN":"invalidation-token-value",
            "GENB_REDIS_HOST":"redis", "GENB_ALLOWED_UPSTREAMS":"agent.internal:18714,memory.internal:8701",
            "GENB_AGENT_CREDENTIALS":"agent-a=agent-machine-value", "MEMORY_TOKEN":"memory-secret-value",
        }
        app = build_gateway(environment, clock=lambda: datetime(2026, 8, 13, 13, tzinfo=timezone.utc),
                            control_plane=Control(), redis=Redis())
        self.assertEqual(7, app.runtime_state.current(risk="HIGH").config_version)
        self.assertEqual("http://agent.internal:18714", app.routes.resolve("agent-a").upstream)
        self.assertIs(app.runtime_state, app.capability_invocation.capabilities)
        self.assertEqual("memory-secret-value", app.capability_invocation.secret_resolver.resolve("env://MEMORY_TOKEN"))
        self.assertEqual(200, get(app, "/health/live"))
        self.assertEqual(200, get(app, "/health/ready"))


if __name__ == "__main__": unittest.main()
