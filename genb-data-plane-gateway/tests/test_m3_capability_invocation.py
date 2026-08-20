from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timedelta, timezone
import unittest

from genb_gateway.app import GatewaySettings, create_app
from genb_gateway.capabilities import (
    AdapterRegistry, AdapterResponse, CapabilityInvocationModule, OperationPolicy,
    InMemoryIdempotencyStore, InMemoryRateLimiter, MappingSecretResolver, PublishedCapability, PublishedCapabilityTable,
    StaticActorTokenProvider,
)
from genb_gateway.control import FakeControlPlane
from genb_gateway.identity import IdentityTokens
from genb_gateway.routing import PublishedRouteTable
from genb_gateway.sessions import InMemorySessionStore


class AsgiClient:
    def __init__(self, app) -> None: self.app = app

    def post(self, path: str, *, headers: dict[str, str], value: dict):
        sent = []; delivered = False; body = json.dumps(value).encode()
        async def receive():
            nonlocal delivered
            if delivered: return {"type": "http.disconnect"}
            delivered = True; return {"type": "http.request", "body": body, "more_body": False}
        async def send(message): sent.append(message)
        scope = {"type":"http","asgi":{"version":"3.0"},"http_version":"1.1","method":"POST",
                 "scheme":"http","path":path,"raw_path":path.encode(),"query_string":b"",
                 "headers":[(key.lower().encode(), val.encode()) for key,val in headers.items()],
                 "server":("gateway.local",80),"client":("127.0.0.1",12345)}
        asyncio.run(self.app(scope, receive, send))
        start = sent[0]; response_headers = {k.decode():v.decode() for k,v in start["headers"]}
        response_body = b"".join(message.get("body",b"") for message in sent[1:])
        self.last_body_messages = [message for message in sent[1:] if message["type"] == "http.response.body"]
        return start["status"], response_headers, response_body


class M3CapabilityInvocationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = lambda: datetime(2026, 8, 13, 3, 0, tzinfo=timezone.utc)
        self.sessions = InMemorySessionStore(self.clock)
        self.identity = IdentityTokens(self.clock, timedelta(seconds=60))
        self.module = CapabilityInvocationModule(
            capabilities=PublishedCapabilityTable([]),
            adapters=AdapterRegistry(),
            agent_credentials={"agent-a": "agent-machine-secret"},
            identity=self.identity,
            sessions=self.sessions,
            clock=self.clock,
        )
        self.app = create_app(
            settings=GatewaySettings("http://gateway.local", "http://portal.local/authorize",
                                    "http://gateway.local/agents/_auth/callback", "nginx-only", cookie_secure=False),
            control_plane=FakeControlPlane(),
            routes=PublishedRouteTable(routes=[], allowed_upstreams=frozenset()),
            clock=self.clock,
            session_store=self.sessions,
            identity_tokens=self.identity,
            capability_invocation=self.module,
        )
        opaque = self.app.sessions.create(
            ttl=timedelta(hours=8), session_id="session-a", tenant_id="tenant-1", user_id="user-a",
            username="alice", agent_id="agent-a", session_grant="g" * 40,
        )
        self.identity_token = self.app.identity.issue(self.app.sessions.resolve(opaque))
        self.client = AsgiClient(self.app)

    def invoke(self, capability: str, operation: str, *, payload=None, extra_headers=None):
        headers = {"authorization": f"Bearer {self.identity_token}",
                   "x-genb-agent-credential": "agent-machine-secret", "content-type": "application/json"}
        headers.update(extra_headers or {})
        return self.client.post(
            f"/component-api/v1/capabilities/{capability}/operations/{operation}:invoke",
            headers=headers,
            value={"schemaVersion":"1.0","context":{"requestId":"m3-request-1","conversationId":"conversation-1"},
                   "payload": payload or {}},
        )

    def test_valid_identity_cannot_invoke_an_unbound_capability(self) -> None:
        status, headers, body = self.invoke("SHORT_TERM_MEMORY", "appendMessage")
        self.assertEqual(403, status, body)
        self.assertEqual("application/problem+json", headers["content-type"])
        problem = json.loads(body)
        self.assertEqual("CAPABILITY_NOT_BOUND", problem["code"])
        self.assertEqual("m3-request-1", problem["requestId"])

    def test_wrong_machine_credential_and_revoked_session_fail_closed(self) -> None:
        wrong = self.invoke("SHORT_TERM_MEMORY", "read", extra_headers={"x-genb-agent-credential":"wrong"})
        self.assertEqual(401, wrong[0])
        self.assertEqual("INVALID_AGENT_IDENTITY", json.loads(wrong[2])["code"])

        opaque = self.sessions.create(
            ttl=timedelta(hours=1), session_id="revoked-session", tenant_id="tenant-1", user_id="user-r",
            username="revoked", agent_id="agent-a", session_grant="r" * 40,
        )
        self.identity_token = self.identity.issue(self.sessions.resolve(opaque))
        self.sessions.revoke(opaque)
        revoked = self.invoke("SHORT_TERM_MEMORY", "read")
        self.assertEqual(401, revoked[0])
        self.assertEqual("INVALID_IDENTITY_TOKEN", json.loads(revoked[2])["code"])

    def test_published_binding_invokes_compiled_adapter_with_signed_subject(self) -> None:
        class SubjectEchoAdapter:
            def invoke(self, request):
                return AdapterResponse.json(200, {
                    "subject": request.subject.user_id,
                    "agentId": request.subject.agent_id,
                    "message": request.payload["message"],
                })

        adapters = AdapterRegistry()
        adapters.register("TEST_SUBJECT_ECHO", "1.0.0", SubjectEchoAdapter())
        self.module.adapters = adapters
        self.module.capabilities.replace([PublishedCapability(
            agent_id="agent-a", capability_code="SHORT_TERM_MEMORY", implementation_code="short-memory-v1",
            adapter_code="TEST_SUBJECT_ECHO", adapter_version="1.0.0", upstream_ref="upstream://short-memory",
            credential_ref=None, isolation_mode="SUBJECT_KEYS", status="PUBLISHED",
            operations=(OperationPolicy("appendMessage", 1000, "NONE", "JSON", 4096),),
        )])

        status, headers, body = self.invoke("SHORT_TERM_MEMORY", "appendMessage", payload={
            "message": "hello", "userId": "forged-admin", "agentId": "forged-agent",
        })
        self.assertEqual(200, status, body)
        self.assertEqual("application/json", headers["content-type"])
        self.assertEqual({"subject":"user-a","agentId":"agent-a","message":"hello"}, json.loads(body))
        self.assertNotIn(b"forged-admin", body)

    def test_disabled_implementation_fails_before_adapter_invocation(self) -> None:
        class MustNotRun:
            def invoke(self, request): raise AssertionError("disabled implementation reached Adapter")
        adapters = AdapterRegistry(); adapters.register("TEST_DISABLED", "1.0.0", MustNotRun())
        self.module.adapters = adapters
        self.module.capabilities.replace([PublishedCapability(
            "agent-a", "PLANNING_REASONING", "planning-disabled", "TEST_DISABLED", "1.0.0",
            "upstream://planning", None, "SUBJECT_KEYS", "DISABLED",
            (OperationPolicy("analyzeRequirement", 1000, "NONE", "JSON", 4096),),
        )])
        status, _, body = self.invoke("PLANNING_REASONING", "analyzeRequirement")
        self.assertEqual(503, status, body)
        self.assertEqual("IMPLEMENTATION_UNAVAILABLE", json.loads(body)["code"])

    def test_unknown_operation_and_oversized_payload_fail_before_adapter(self) -> None:
        class MustNotRun:
            def invoke(self, request): raise AssertionError("invalid operation reached Adapter")
        adapters = AdapterRegistry(); adapters.register("TEST_BOUNDS", "1.0.0", MustNotRun())
        self.module.adapters = adapters
        self.module.capabilities.replace([PublishedCapability(
            "agent-a", "SHORT_TERM_MEMORY", "short-v1", "TEST_BOUNDS", "1.0.0", "upstream://short",
            None, "SUBJECT_KEYS", "PUBLISHED", (OperationPolicy("appendMessage", 1000, "NONE", "JSON", 16),),
        )])
        unknown = self.invoke("SHORT_TERM_MEMORY", "deleteEverything")
        self.assertEqual(404, unknown[0])
        self.assertEqual("OPERATION_NOT_FOUND", json.loads(unknown[2])["code"])
        oversized = self.invoke("SHORT_TERM_MEMORY", "appendMessage", payload={"message": "x" * 40})
        self.assertEqual(413, oversized[0])
        self.assertEqual("REQUEST_TOO_LARGE", json.loads(oversized[2])["code"])

    def test_rate_limit_is_isolated_by_signed_user_subject(self) -> None:
        class Echo:
            def invoke(self, request): return AdapterResponse.json(200, {"userId": request.subject.user_id})
        adapters = AdapterRegistry(); adapters.register("TEST_RATE", "1.0.0", Echo())
        self.module.adapters = adapters
        self.module.rate_limiter = InMemoryRateLimiter(self.clock, limit=2, window=timedelta(minutes=1))
        self.module.capabilities.replace([PublishedCapability(
            "agent-a", "SHORT_TERM_MEMORY", "short-v1", "TEST_RATE", "1.0.0", "upstream://short",
            None, "SUBJECT_KEYS", "PUBLISHED", (OperationPolicy("read", 1000, "READ", "JSON", 4096),),
        )])
        self.assertEqual(200, self.invoke("SHORT_TERM_MEMORY", "read")[0])
        self.assertEqual(200, self.invoke("SHORT_TERM_MEMORY", "read")[0])
        limited = self.invoke("SHORT_TERM_MEMORY", "read")
        self.assertEqual(429, limited[0])
        self.assertEqual("RATE_LIMITED", json.loads(limited[2])["code"])

        other_cookie = self.sessions.create(
            ttl=timedelta(hours=8), session_id="session-b", tenant_id="tenant-1", user_id="user-b",
            username="bob", agent_id="agent-a", session_grant="h" * 40,
        )
        self.identity_token = self.identity.issue(self.sessions.resolve(other_cookie))
        status, _, body = self.invoke("SHORT_TERM_MEMORY", "read")
        self.assertEqual(200, status, body)
        self.assertEqual("user-b", json.loads(body)["userId"])

    def test_upstream_failure_never_leaks_secret_actor_token_or_real_address(self) -> None:
        class FailingExternalAdapter:
            def invoke(self, request):
                if request.credential != "service-secret-value" or request.actor_token != "actor-token-value":
                    return AdapterResponse.json(418, {"code":"CREDENTIAL_INJECTION_MISSING"})
                raise RuntimeError(
                    "http://internal-planning:18712 failed api-key=service-secret-value actor-token=actor-token-value"
                )
        adapters = AdapterRegistry(); adapters.register("TEST_FAILURE", "1.0.0", FailingExternalAdapter())
        self.module.adapters = adapters
        self.module.secret_resolver = MappingSecretResolver({"secret://planning/client": "service-secret-value"})
        self.module.actor_tokens = StaticActorTokenProvider("actor-token-value")
        self.module.capabilities.replace([PublishedCapability(
            "agent-a", "PLANNING_REASONING", "planning-v1", "TEST_FAILURE", "1.0.0",
            "upstream://planning", "secret://planning/client", "SUBJECT_KEYS", "PUBLISHED",
            (OperationPolicy("analyzeRequirement", 1000, "NONE", "JSON", 4096),),
        )])
        status, headers, body = self.invoke("PLANNING_REASONING", "analyzeRequirement")
        self.assertEqual(503, status)
        self.assertEqual("application/problem+json", headers["content-type"])
        self.assertEqual("UPSTREAM_UNAVAILABLE", json.loads(body)["code"])
        for marker in (b"service-secret", b"actor-token", b"api-key", b"internal-planning", b"18712"):
            self.assertNotIn(marker, body.lower())

    def test_required_idempotency_key_replays_once_and_rejects_conflicting_payload(self) -> None:
        class CountingWriteAdapter:
            count = 0
            def invoke(self, request):
                self.count += 1
                return AdapterResponse.json(200, {"writeCount": self.count, "message": request.payload["message"]})
        adapter = CountingWriteAdapter(); adapters = AdapterRegistry()
        adapters.register("TEST_IDEMPOTENT_WRITE", "1.0.0", adapter)
        self.module.adapters = adapters
        self.module.idempotency = InMemoryIdempotencyStore()
        self.module.capabilities.replace([PublishedCapability(
            "agent-a", "SHORT_TERM_MEMORY", "short-v1", "TEST_IDEMPOTENT_WRITE", "1.0.0",
            "upstream://short", None, "SUBJECT_KEYS", "PUBLISHED",
            (OperationPolicy("appendMessage", 1000, "REQUIRED_KEY", "JSON", 4096),),
        )])
        missing_status, _, missing_body = self.invoke("SHORT_TERM_MEMORY", "appendMessage", payload={"message":"one"})
        self.assertEqual(400, missing_status)
        self.assertEqual("IDEMPOTENCY_KEY_REQUIRED", json.loads(missing_body)["code"])
        first = self.invoke("SHORT_TERM_MEMORY", "appendMessage", payload={"message":"one"},
                            extra_headers={"idempotency-key":"write-001"})
        replay = self.invoke("SHORT_TERM_MEMORY", "appendMessage", payload={"message":"one"},
                             extra_headers={"idempotency-key":"write-001"})
        self.assertEqual((200, json.loads(first[2])), (200, json.loads(replay[2])))
        self.assertEqual(1, json.loads(first[2])["writeCount"])
        conflict = self.invoke("SHORT_TERM_MEMORY", "appendMessage", payload={"message":"different"},
                               extra_headers={"idempotency-key":"write-001"})
        self.assertEqual(409, conflict[0])
        self.assertEqual("IDEMPOTENCY_CONFLICT", json.loads(conflict[2])["code"])

    def test_operation_timeout_is_enforced_and_normalized_as_retriable(self) -> None:
        release = threading.Event()
        class BlockingAdapter:
            def invoke(self, request):
                release.wait(1)
                return AdapterResponse.json(200, {"tooLate": True})
        adapters = AdapterRegistry(); adapters.register("TEST_TIMEOUT", "1.0.0", BlockingAdapter())
        self.module.adapters = adapters
        self.module.capabilities.replace([PublishedCapability(
            "agent-a", "LONG_TERM_MEMORY", "long-v1", "TEST_TIMEOUT", "1.0.0", "upstream://long",
            None, "SUBJECT_KEYS", "PUBLISHED", (OperationPolicy("searchMemories", 10, "READ", "JSON", 4096),),
        )])
        status, _, body = self.invoke("LONG_TERM_MEMORY", "searchMemories")
        release.set()
        self.assertEqual(504, status, body)
        problem = json.loads(body)
        self.assertEqual("UPSTREAM_TIMEOUT", problem["code"])
        self.assertTrue(problem["retriable"])

    def test_repeated_upstream_failures_open_circuit_before_next_adapter_call(self) -> None:
        class AlwaysFailAdapter:
            count = 0
            def invoke(self, request):
                self.count += 1
                raise ConnectionError("internal secret-bearing upstream failed")
        adapter = AlwaysFailAdapter(); adapters = AdapterRegistry(); adapters.register("TEST_BREAKER", "1.0.0", adapter)
        self.module.adapters = adapters
        self.module.capabilities.replace([PublishedCapability(
            "agent-a", "PLANNING_REASONING", "planning-v1", "TEST_BREAKER", "1.0.0", "upstream://planning",
            None, "SUBJECT_KEYS", "PUBLISHED", (OperationPolicy("analyzeRequirement", 100, "NONE", "JSON", 4096),),
        )])
        for _ in range(3):
            self.assertEqual("UPSTREAM_UNAVAILABLE", json.loads(self.invoke(
                "PLANNING_REASONING", "analyzeRequirement")[2])["code"])
        fourth = self.invoke("PLANNING_REASONING", "analyzeRequirement")
        self.assertEqual(503, fourth[0])
        self.assertEqual("CIRCUIT_OPEN", json.loads(fourth[2])["code"])
        self.assertEqual(3, adapter.count)

    def test_sse_operation_is_sent_as_multiple_asgi_body_chunks(self) -> None:
        class StreamingAdapter:
            def invoke(self, request):
                return AdapterResponse.stream((b"event: token\ndata: one\n\n", b"event: done\ndata: ok\n\n"))
        adapters = AdapterRegistry(); adapters.register("TEST_SSE", "1.0.0", StreamingAdapter())
        self.module.adapters = adapters
        self.module.capabilities.replace([PublishedCapability(
            "agent-a", "PLANNING_REASONING", "planning-stream", "TEST_SSE", "1.0.0", "upstream://planning",
            None, "SUBJECT_KEYS", "PUBLISHED", (OperationPolicy("streamPlan", 1000, "NONE", "SSE", 4096),),
        )])
        status, headers, body = self.invoke("PLANNING_REASONING", "streamPlan")
        self.assertEqual(200, status)
        self.assertEqual("text/event-stream", headers["content-type"])
        self.assertEqual(2, len([item for item in self.client.last_body_messages if item.get("body")]))
        self.assertIn(b"event: done", body)


if __name__ == "__main__": unittest.main()
