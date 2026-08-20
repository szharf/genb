from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from genb_gateway.adapters import HeterogeneousFakeAdapter, UrllibHttpTransport
from genb_gateway.app import GatewaySettings, create_app
from genb_gateway.capabilities import (
    AdapterRegistry, CapabilityInvocationModule, MappingSecretResolver, OperationPolicy,
    PublishedCapability, PublishedCapabilityTable,
)
from genb_gateway.control import FakeControlPlane
from genb_gateway.identity import IdentityTokens
from genb_gateway.routing import PublishedRouteTable
from genb_gateway.sessions import InMemorySessionStore


class _VendorHandler(BaseHTTPRequestHandler):
    requests: list[dict] = []
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
        payload = json.dumps({"output": {"brief": "brief:" + body["arguments"]["sourceText"]}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/x-vendor+json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers(); self.wfile.write(payload)
    def log_message(self, *_args): return


class _AsgiClient:
    def __init__(self, app) -> None: self.app = app
    def invoke(self, token: str, value: dict):
        sent = []; delivered = False; body = json.dumps(value).encode()
        async def receive():
            nonlocal delivered
            if delivered: return {"type": "http.disconnect"}
            delivered = True; return {"type": "http.request", "body": body, "more_body": False}
        async def send(message): sent.append(message)
        path = "/component-api/v1/capabilities/FEEDBACK_LOOP/operations/summarize:invoke"
        scope = {"type":"http", "method":"POST", "path":path, "query_string":b"", "headers":[
            (b"authorization", ("Bearer " + token).encode()),
            (b"x-genb-agent-credential", b"agent-machine-secret"),
            (b"content-type", b"application/json"),
        ]}
        asyncio.run(self.app(scope, receive, send))
        return sent[0]["status"], b"".join(item.get("body", b"") for item in sent[1:])


class M3HeterogeneousFakeE2ETest(unittest.TestCase):
    def test_two_users_reach_one_nonstandard_service_with_distinct_anonymous_subjects(self) -> None:
        _VendorHandler.requests = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), _VendorHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            clock = lambda: datetime(2026, 8, 13, 4, tzinfo=timezone.utc)
            sessions = InMemorySessionStore(clock); identity = IdentityTokens(clock, timedelta(seconds=60))
            adapters = AdapterRegistry(); adapters.register(
                "HETEROGENEOUS_FAKE", "1.0.0", HeterogeneousFakeAdapter(UrllibHttpTransport())
            )
            module = CapabilityInvocationModule(
                capabilities=PublishedCapabilityTable([PublishedCapability(
                    "agent-a", "FEEDBACK_LOOP", "vendor-brief-v7", "HETEROGENEOUS_FAKE", "1.0.0",
                    f"http://127.0.0.1:{server.server_port}", "env://VENDOR_TOKEN", "SUBJECT_KEYS", "PUBLISHED",
                    (OperationPolicy("summarize", 1000, "NONE", "JSON", 4096),),
                )]), adapters=adapters, agent_credentials={"agent-a":"agent-machine-secret"},
                identity=identity, sessions=sessions, clock=clock,
                secret_resolver=MappingSecretResolver({"env://VENDOR_TOKEN":"vendor-secret"}),
            )
            app = create_app(
                settings=GatewaySettings("http://gateway.local", "http://portal.local", "http://gateway.local/callback",
                                         "nginx", cookie_secure=False),
                control_plane=FakeControlPlane(),
                routes=PublishedRouteTable(routes=[], allowed_upstreams=frozenset()), clock=clock,
                session_store=sessions, identity_tokens=identity, capability_invocation=module,
            )
            client = _AsgiClient(app)
            responses = []
            for suffix in ("a", "b"):
                cookie = sessions.create(
                    ttl=timedelta(hours=1), session_id="session-" + suffix, tenant_id="tenant-1",
                    user_id="user-" + suffix, username=suffix, agent_id="agent-a", session_grant=suffix * 40,
                )
                token = identity.issue(sessions.resolve(cookie))
                responses.append(client.invoke(token, {
                    "schemaVersion":"1.0", "context":{"requestId":"req-" + suffix, "conversationId":"conv-" + suffix},
                    "payload":{"text":"message-" + suffix},
                }))
            self.assertEqual([200, 200], [item[0] for item in responses])
            self.assertEqual({"summary":"brief:message-a"}, json.loads(responses[0][1]))
            self.assertEqual("/v7/execute", _VendorHandler.requests[0]["path"])
            self.assertEqual("vendor-secret", _VendorHandler.requests[0]["headers"]["X-Vendor-Key"])
            subjects = [item["body"]["subjectKey"] for item in _VendorHandler.requests]
            self.assertNotEqual(subjects[0], subjects[1])
            self.assertTrue(all(item.startswith("sha256:") and "user-" not in item for item in subjects))
            for _, body in responses:
                self.assertNotIn(b"vendor-secret", body)
                self.assertNotIn(str(server.server_port).encode(), body)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)


if __name__ == "__main__": unittest.main()
