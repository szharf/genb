from __future__ import annotations

import json
import os
import base64
import socket
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


BASE = "http://127.0.0.1:18081"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@unittest.skipUnless(os.environ.get("GENB_NGINX_E2E") == "1", "requires local Gate C stack")
class M2NginxEndToEndTest(unittest.TestCase):
    opener = build_opener(NoRedirect)

    def login(self, agent_id: str, code: str, user_path: str) -> str:
        first = self._request(f"/agents/_auth/login?agentId={agent_id}&returnPath=/agents/{agent_id}/{user_path}")
        self.assertEqual(303, first.status)
        state = parse_qs(urlsplit(first.headers["location"]).query)["state"][0]
        callback = self._request(f"/agents/_auth/callback?code={code}&state={state}")
        self.assertEqual(303, callback.status)
        self.assertEqual(f"/agents/{agent_id}/{user_path}", callback.headers["location"])
        return callback.headers["set-cookie"].split(";", 1)[0]

    def test_two_users_two_agents_header_forgery_and_streaming(self) -> None:
        alice = self.login("agent-a", "a" * 40, "events")
        stream = urlopen(Request(BASE + "/agents/agent-a/events", headers={
            "Cookie": alice, "X-GenB-User-Id": "admin", "X-GenB-Upstream": "http://169.254.169.254",
        }), timeout=3)
        self.assertEqual("text/event-stream", stream.headers.get_content_type())
        first_event = stream.readline() + stream.readline() + stream.readline()
        second_event = stream.readline() + stream.readline() + stream.readline()
        stream.close()
        self.assertIn(b"data: first", first_event)
        self.assertIn(b"event: complete", second_event)
        exposed = json.dumps(dict(stream.headers), ensure_ascii=False).lower()
        self.assertNotIn("x-genb", exposed)
        self.assertNotIn("19001", exposed)
        inspected = urlopen(Request(BASE + "/agents/agent-a/inspect", headers={
            "Cookie": alice, "X-GenB-Forged": "browser-controlled",
        }), timeout=3)
        self.assertEqual({"forgedHeaderReceived": False, "gatewayCookieReceived": False, "trustedUserId": "user-a"},
                         json.load(inspected))

        websocket = socket.create_connection(("127.0.0.1", 18081), timeout=3)
        key = base64.b64encode(b"gate-c-websocket").decode()
        websocket.sendall((
            "GET /agents/agent-a/ws HTTP/1.1\r\nHost: 127.0.0.1:18081\r\n"
            f"Cookie: {alice}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode())
        handshake = websocket.recv(4096)
        self.assertIn(b" 101 ", handshake)
        mask = b"\x01\x02\x03\x04"; payload = b"hello"
        websocket.sendall(bytes([0x81, 0x80 | len(payload)]) + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(payload)))
        echoed = websocket.recv(32); websocket.close()
        self.assertEqual(b"hello", echoed[2:2 + (echoed[1] & 0x7f)])

        bob = self.login("agent-b", "b" * 40, "who")
        identity = urlopen(Request(BASE + "/agents/agent-b/who", headers={"Cookie": bob}), timeout=3)
        self.assertEqual({"userId": "user-b", "agentId": "agent-b"}, json.load(identity))
        with self.assertRaises(HTTPError) as denied:
            urlopen(Request(BASE + "/agents/agent-b/who", headers={"Cookie": alice}), timeout=3)
        self.assertEqual(401, denied.exception.code)

    def _request(self, path: str):
        try:
            return self.opener.open(Request(BASE + path), timeout=3)
        except HTTPError as response:
            return response


if __name__ == "__main__":
    unittest.main()
