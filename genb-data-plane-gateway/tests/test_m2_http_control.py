from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from genb_gateway.control import HttpControlPlane


class ControlHandler(BaseHTTPRequestHandler):
    requests = []
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        self.requests.append((self.path, self.headers.get("authorization"), body))
        if self.path.endswith("/exchange"):
            response = json.dumps({"schemaVersion":"1.0","sessionGrant":"g"*40,"tenantId":"tenant-1",
                "userId":7,"username":"alice","agentId":body["agentId"],"sessionId":body["sessionId"],
                "expiresAt":"2026-08-13T18:00:00"}).encode()
            self.send_response(200); self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(response))); self.end_headers(); self.wfile.write(response)
        else:
            self.send_response(204); self.end_headers()
    def log_message(self, format, *args): pass


class M2HttpControlPlaneTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ControlHandler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls): cls.server.shutdown()

    def test_exchange_and_revoke_use_the_single_gateway_machine_identity(self) -> None:
        ControlHandler.requests.clear()
        control = HttpControlPlane(f"http://127.0.0.1:{self.server.server_port}", "machine-only")
        subject = control.exchange(code="a"*40, state="s"*40, agent_id="agent-a",
                                   callback_url="http://gateway/agents/_auth/callback", session_id="session-1")
        self.assertEqual(("tenant-1", "7", "agent-a"), (subject.tenant_id, subject.user_id, subject.agent_id))
        control.revoke("agent-a", "g"*40)
        self.assertEqual(["/api/v1/internal/data-plane/identity/exchange", "/api/v1/internal/data-plane/identity/revoke"],
                         [request[0] for request in ControlHandler.requests])
        self.assertTrue(all(request[1] == "Bearer machine-only" for request in ControlHandler.requests))
        self.assertNotIn("machine-only", json.dumps([request[2] for request in ControlHandler.requests]))


if __name__ == "__main__": unittest.main()
