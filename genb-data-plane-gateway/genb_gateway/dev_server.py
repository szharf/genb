from __future__ import annotations

import argparse
import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from urllib.parse import urlsplit

from .app import GatewaySettings, create_app
from .capabilities import (
    AdapterRegistry, AdapterResponse, CapabilityInvocationModule, OperationPolicy,
    PublishedCapability, PublishedCapabilityTable, StaticActorTokenProvider,
)
from .control import FakeControlPlane
from .fake_agents import IdentityAwareFakeAgent, StatelessFakeAgent
from .identity import IdentityTokens
from .routing import PublishedAgentRoute, PublishedRouteTable
from .sessions import InMemorySessionStore


class M5ExperienceAdapter:
    """Stateful local acceptance Adapter for the three 18714 browser experiences."""
    def __init__(self) -> None:
        self.turns = {}; self.memories = {}

    def invoke(self, request):
        operation, payload = request.operation.operation_id, request.payload
        subject = (request.subject.tenant_id, request.subject.user_id, request.subject.agent_id)
        conversation = (subject, request.conversation_id)
        if operation == "prepareShortTermContext":
            return AdapterResponse.json(200, {"data":{"messages":self.turns.get(conversation, [])}})
        if operation == "commitShortTermTurn":
            self.turns.setdefault(conversation, []).extend((
                {"role":"user", "content":payload["userMessage"], "turnId":payload["turnId"]},
                {"role":"assistant", "content":payload["assistantMessage"], "turnId":payload["turnId"]},
            ))
            return AdapterResponse.json(200, {"data":{"messageCount":len(self.turns[conversation]), "replayed":False}})
        if operation == "createConversationMemoryExtraction":
            self.memories[subject] = payload["userMessage"]
            return AdapterResponse.json(202, {"data":{"extractionId":"local-extraction"}})
        if operation == "getLongTermExtraction":
            return AdapterResponse.json(200, {"data":{"status":"SUCCEEDED", "writtenCount":1, "rejectedCount":0}})
        if operation == "searchLongTermMemories":
            content = self.memories.get(subject)
            items = [] if content is None else [{"memoryId":"local-memory", "type":"USER_PREFERENCE",
                "content":content, "confidence":0.99, "sourceType":"CONVERSATION", "sourceRef":"local-turn"}]
            return AdapterResponse.json(200, {"data":{"items":items}})
        if operation == "completeChat":
            message = payload["messages"][-1]["content"]
            intent = "CREATE_SKILL" if "Skill" in message or "skill" in message else "CHAT"
            content = json.dumps({"intent":intent, "answer":"我会继续处理你的需求。", "skill":None}, ensure_ascii=False)
            return AdapterResponse.json(200, {"data":{"content":content, "provider":"LOCAL_FAKE", "model":"m5",
                "usage":{"inputTokens":10, "outputTokens":10}}, "meta":{"requestId":request.request_id}})
        if operation == "converseRequirement":
            message = str(payload.get("message", ""))
            if "PDF" not in message:
                return AdapterResponse.json(200, {"data":{"status":"CLARIFYING", "decisionSummary":"还需要补充输入格式。",
                    "questions":[{"question":"输入材料是什么格式？"}]}})
            return AdapterResponse.json(200, {"data":{"status":"READY", "questions":[], "references":[], "draft":{
                "name":"材料检查", "description":"检查材料完整性", "goal":"生成材料检查表",
                "expectedInputs":["PDF"], "expectedOutputs":["Markdown"], "constraints":["不修改原文件"],
                "preferredTools":[], "toolReferences":[], "riskLevel":"LOW"}}})
        if operation == "generateSkill":
            return AdapterResponse.json(200, {"data":{"name":payload["name"], "content":"# 材料检查",
                "validation":{"valid":True, "issues":[]}}})
        raise LookupError("local M5 operation unavailable")


class AsgiHandler(BaseHTTPRequestHandler):
    app = None
    protocol_version = "HTTP/1.1"

    def do_GET(self): self._dispatch()
    def do_POST(self): self._dispatch()

    def _dispatch(self) -> None:
        split = urlsplit(self.path)
        if split.path == "/ws" and self.headers.get("upgrade", "").lower() == "websocket":
            return self._websocket()
        body_length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(body_length) if body_length else b""
        received = False
        started = False

        async def receive():
            nonlocal received
            if received:
                return {"type": "http.disconnect"}
            received = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                self.send_response(message["status"])
                for key, value in message.get("headers", []):
                    self.send_header(key.decode(), value.decode())
                self.end_headers(); started = True
            elif message["type"] == "http.response.body":
                if message.get("body"):
                    self.wfile.write(message["body"]); self.wfile.flush()

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": self.command,
            "scheme": "http", "path": split.path, "raw_path": split.path.encode(),
            "query_string": split.query.encode(), "headers": [(k.lower().encode(), v.encode()) for k, v in self.headers.items()],
            "server": self.server.server_address, "client": self.client_address,
        }
        asyncio.run(self.app(scope, receive, send))
        if not started:
            self.send_error(500)

    def _websocket(self) -> None:
        key = self.headers.get("sec-websocket-key", "")
        if not key:
            return self.send_error(400)
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        first = self.rfile.read(2)
        if len(first) != 2:
            return
        length = first[1] & 0x7f
        if length == 126:
            length = int.from_bytes(self.rfile.read(2), "big")
        elif length == 127:
            length = int.from_bytes(self.rfile.read(8), "big")
        mask = self.rfile.read(4) if first[1] & 0x80 else b""
        payload = self.rfile.read(length)
        if mask:
            payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        prefix = bytes([0x81, len(payload)]) if len(payload) < 126 else bytes([0x81, 126]) + len(payload).to_bytes(2, "big")
        self.wfile.write(prefix + payload); self.wfile.flush()

    def log_message(self, format, *args) -> None:
        pass


def _serve(port: int, app) -> ThreadingHTTPServer:
    handler = type(f"Handler{port}", (AsgiHandler,), {"app": app})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ready-file")
    args = parser.parse_args()
    control = FakeControlPlane()
    control.add_code(code="a" * 40, state=None, agent_id="agent-a", tenant_id="tenant-1",
                     user_id="user-a", username="alice", session_grant="g" * 40)
    control.add_code(code="b" * 40, state=None, agent_id="agent-b", tenant_id="tenant-1",
                     user_id="user-b", username="bob", session_grant="h" * 40)
    control.add_code(code="c" * 40, state=None, agent_id="core-component-demo-agent", tenant_id="tenant-1",
                     user_id="42", username="customer", session_grant="i" * 40)
    routes = PublishedRouteTable(routes=[
        PublishedAgentRoute("agent-a", "http://127.0.0.1:19001", "NONE", frozenset({"user-a"})),
        PublishedAgentRoute("agent-b", "http://127.0.0.1:19002", "SIGNED_TOKEN", frozenset({"user-b"})),
        PublishedAgentRoute("core-component-demo-agent", "http://127.0.0.1:18714", "SIGNED_TOKEN", frozenset({"42"})),
    ], allowed_upstreams=frozenset({("127.0.0.1", 18714), ("127.0.0.1", 19001), ("127.0.0.1", 19002)}))
    clock = lambda: datetime.now(timezone.utc)
    sessions = InMemorySessionStore(clock)
    identity = IdentityTokens(clock, timedelta(seconds=60))
    adapter = M5ExperienceAdapter(); adapters = AdapterRegistry(); adapters.register("M5_EXPERIENCE", "1.0.0", adapter)
    policies = {
        "SHORT_TERM_MEMORY": (("prepareShortTermContext", "READ"), ("commitShortTermTurn", "REQUIRED_KEY")),
        "LONG_TERM_MEMORY": (("createConversationMemoryExtraction", "REQUIRED_KEY"),
                             ("getLongTermExtraction", "READ"), ("searchLongTermMemories", "READ")),
        "PLANNING_REASONING": (("converseRequirement", "NONE"), ("generateSkill", "REQUIRED_KEY")),
        "INFERENCE_ENGINE": (("completeChat", "NONE"),),
    }
    bindings = [PublishedCapability(
        "core-component-demo-agent", capability, "m5-local", "M5_EXPERIENCE", "1.0.0", "upstream://local",
        None, "SUBJECT_KEYS", "PUBLISHED", tuple(OperationPolicy(operation, 1000, idempotency, "JSON", 65536)
                                                  for operation, idempotency in operations),
    ) for capability, operations in policies.items()]
    capabilities = CapabilityInvocationModule(
        capabilities=PublishedCapabilityTable(bindings), adapters=adapters,
        agent_credentials={"core-component-demo-agent":"core-machine"}, identity=identity, sessions=sessions,
        clock=clock, actor_tokens=StaticActorTokenProvider("local-actor"),
    )
    gateway = create_app(settings=GatewaySettings(
        public_origin="http://127.0.0.1:18081", portal_authorize_url="http://portal.local/agent-authorize",
        callback_url="http://127.0.0.1:18081/agents/_auth/callback", nginx_token="nginx-only",
        cookie_secure=False, session_ttl=timedelta(hours=8), identity_ttl=timedelta(seconds=60),
    ), control_plane=control, routes=routes, clock=clock, session_store=sessions, identity_tokens=identity,
       capability_invocation=capabilities)
    servers = [_serve(18080, gateway), _serve(19001, StatelessFakeAgent()),
               _serve(19002, IdentityAwareFakeAgent(gateway.identity.verify, "agent-b"))]
    if args.ready_file:
        open(args.ready_file, "w", encoding="utf-8").write("ready")
    try:
        threading.Event().wait()
    finally:
        for server in servers: server.shutdown()


if __name__ == "__main__":
    main()
