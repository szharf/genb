from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import gc
import json
import statistics
import time
import tracemalloc
import unittest
from urllib.parse import urlencode

from genb_gateway.app import GatewaySettings, create_app
from genb_gateway.capabilities import (
    AdapterRegistry, AdapterResponse, CapabilityInvocationModule, OperationPolicy,
    PublishedCapability, PublishedCapabilityTable, StaticActorTokenProvider,
)
from genb_gateway.control import FakeControlPlane
from genb_gateway.identity import IdentityTokens
from genb_gateway.routing import PublishedAgentRoute, PublishedRouteTable
from genb_gateway.sessions import InMemorySessionStore


class PublicAsgiClient:
    def __init__(self, app): self.app = app

    def request(self, method: str, path: str, *, headers=None, value=None):
        sent = []; delivered = False
        body = b"" if value is None else json.dumps(value, separators=(",", ":")).encode()

        async def receive():
            nonlocal delivered
            if delivered: return {"type": "http.disconnect"}
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message): sent.append(message)

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
            "scheme": "http", "path": path.split("?", 1)[0], "raw_path": path.split("?", 1)[0].encode(),
            "query_string": path.split("?", 1)[1].encode() if "?" in path else b"",
            "headers": [(key.lower().encode(), val.encode()) for key, val in (headers or {}).items()],
            "server": ("gateway.local", 80), "client": ("127.0.0.1", 12345),
        }
        asyncio.run(self.app(scope, receive, send))
        start = next(item for item in sent if item["type"] == "http.response.start")
        response_headers = {key.decode().lower(): val.decode() for key, val in start["headers"]}
        chunks = [item.get("body", b"") for item in sent if item["type"] == "http.response.body" and item.get("body")]
        return start["status"], response_headers, b"".join(chunks), chunks


class QualityAdapter:
    def invoke(self, request):
        if request.operation.response_mode == "SSE":
            return AdapterResponse.stream((b"event: token\ndata: ok\n\n", b"event: done\ndata: ok\n\n"))
        return AdapterResponse.json(200, {"userId": request.subject.user_id, "agentId": request.subject.agent_id})


class M5QualityGateTest(unittest.TestCase):
    USERS = 20
    SESSIONS = 100

    def setUp(self):
        self.clock = lambda: datetime(2026, 8, 13, 13, tzinfo=timezone.utc)
        self.sessions = InMemorySessionStore(self.clock)
        self.identity = IdentityTokens(self.clock, timedelta(seconds=60))
        routes = []
        bindings = []
        credentials = {}
        adapters = AdapterRegistry(); adapters.register("QUALITY", "1.0.0", QualityAdapter())
        self.active = []
        self.created_sessions = []
        for index in range(self.USERS):
            user_id, agent_id = f"user-{index}", f"agent-{index}"
            routes.append(PublishedAgentRoute(agent_id, f"http://127.0.0.1:{19000 + index}", "SIGNED_TOKEN",
                                              frozenset({user_id})))
            bindings.append(PublishedCapability(
                agent_id, "QUALITY", f"quality-{index}", "QUALITY", "1.0.0", f"upstream://quality-{index}",
                None, "SUBJECT_KEYS", "PUBLISHED",
                (OperationPolicy("read", 1000, "READ", "JSON", 4096),
                 OperationPolicy("stream", 1000, "NONE", "SSE", 4096)),
            ))
            credentials[agent_id] = f"machine-{index}"
            for session_index in range(self.SESSIONS // self.USERS):
                token = self.sessions.create(
                    ttl=timedelta(hours=8), session_id=f"session-{index}-{session_index}", tenant_id="tenant-1",
                    user_id=user_id, username=user_id, agent_id=agent_id, session_grant=f"grant-{index}-{session_index}",
                )
                self.created_sessions.append(token)
                if session_index == 0:
                    session = self.sessions.resolve(token)
                    self.active.append((token, self.identity.issue(session), user_id, agent_id))
        route_table = PublishedRouteTable(
            routes=routes, allowed_upstreams=frozenset(("127.0.0.1", 19000 + i) for i in range(self.USERS)),
        )
        module = CapabilityInvocationModule(
            capabilities=PublishedCapabilityTable(bindings), adapters=adapters, agent_credentials=credentials,
            identity=self.identity, sessions=self.sessions, clock=self.clock,
            actor_tokens=StaticActorTokenProvider("quality-actor-token"),
        )
        self.app = create_app(
            settings=GatewaySettings("http://gateway.local", "http://portal.local/authorize",
                                     "http://gateway.local/agents/_auth/callback", "nginx-only", cookie_secure=False),
            control_plane=FakeControlPlane(), routes=route_table, clock=self.clock, session_store=self.sessions,
            identity_tokens=self.identity, capability_invocation=module,
        )
        self.client = PublicAsgiClient(self.app)

    @staticmethod
    def p95(samples):
        return statistics.quantiles(samples, n=100, method="inclusive")[94]

    def authorize(self, record):
        token, _, _, agent_id = record
        started = time.perf_counter()
        status, _, _, _ = self.client.request(
            "GET", "/internal/agent-access/authorize?" + urlencode({"agentId": agent_id, "requestPath": "/chat"}),
            headers={"x-genb-nginx-identity": "nginx-only", "cookie": f"genb_gateway_session={token}"},
        )
        return status, (time.perf_counter() - started) * 1000

    def invoke(self, record, operation="read"):
        _, identity, user_id, agent_id = record
        started = time.perf_counter()
        result = self.client.request(
            "POST", f"/component-api/v1/capabilities/QUALITY/operations/{operation}:invoke",
            headers={"authorization": f"Bearer {identity}", "x-genb-agent-credential": agent_id.replace("agent", "machine"),
                     "content-type": "application/json"},
            value={"schemaVersion": "1.0", "context": {"requestId": f"req-{user_id}-{operation}",
                                                          "conversationId": f"conv-{user_id}"}, "payload": {}},
        )
        return result, (time.perf_counter() - started) * 1000

    def test_twenty_active_users_and_one_hundred_sessions_meet_access_latency(self):
        self.assertEqual(self.SESSIONS, len(self.created_sessions))
        with ThreadPoolExecutor(max_workers=self.USERS) as pool:
            results = list(pool.map(self.authorize, self.active))
        self.assertEqual([204] * self.USERS, [item[0] for item in results])
        latency = self.p95([item[1] for item in results])
        print(f"M5_ACCESS_P95_MS={latency:.3f}")
        self.assertLess(latency, 10.0)

    def test_twenty_components_sse_and_repeated_calls_meet_resource_gate(self):
        with ThreadPoolExecutor(max_workers=self.USERS) as pool:
            results = list(pool.map(self.invoke, self.active))
        self.assertEqual([200] * self.USERS, [item[0][0] for item in results])
        latency = self.p95([item[1] for item in results])
        print(f"M5_CAPABILITY_P95_MS={latency:.3f}")
        self.assertLess(latency, 50.0)
        self.assertEqual({f"user-{index}" for index in range(self.USERS)},
                         {json.loads(item[0][2])["userId"] for item in results})

        with ThreadPoolExecutor(max_workers=self.USERS) as pool:
            streams = list(pool.map(lambda record: self.invoke(record, "stream"), self.active))
        self.assertTrue(all(result[0][0] == 200 and len(result[0][3]) == 2
                            and b"event: done" in result[0][2] for result in streams))

        for _ in range(50): self.invoke(self.active[0])
        gc.collect(); tracemalloc.start(); baseline = tracemalloc.get_traced_memory()[0]
        for _ in range(500): self.invoke(self.active[0])
        gc.collect(); growth = tracemalloc.get_traced_memory()[0] - baseline; tracemalloc.stop()
        print(f"M5_TRACEMALLOC_GROWTH_BYTES={growth}")
        self.assertLess(growth, 2 * 1024 * 1024)


if __name__ == "__main__": unittest.main()
