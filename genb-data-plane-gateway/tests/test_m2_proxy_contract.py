from __future__ import annotations

import asyncio
import json
from pathlib import Path
import unittest

from genb_gateway.fake_agents import IdentityAwareFakeAgent, StatelessFakeAgent


ROOT = Path(__file__).resolve().parents[1]


async def call(app, *, path="/", headers=None):
    sent = []
    delivered = False
    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message): sent.append(message)
    scope = {"type": "http", "method": "GET", "path": path, "query_string": b"", "headers": [
        (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
    ]}
    await app(scope, receive, send)
    start = sent[0]
    return start["status"], {k.decode(): v.decode() for k, v in start["headers"]}, [m.get("body", b"") for m in sent[1:]]


class M2ProxyContractTest(unittest.TestCase):
    def test_nginx_uses_auth_request_and_direct_streaming_proxy(self) -> None:
        config = (ROOT / "nginx" / "genb-gateway.local.conf").read_text(encoding="utf-8")
        required = [
            "auth_request /_genb_agent_authorize", "auth_request_set $agent_upstream",
            "proxy_pass $agent_upstream", "proxy_buffering off", "proxy_request_buffering off",
            "proxy_pass_request_headers off",
            "proxy_http_version 1.1", "proxy_set_header Upgrade $http_upgrade",
            "proxy_hide_header X-GenB-Upstream", "proxy_hide_header X-GenB-Identity-Token",
            "proxy_set_header X-GenB-User-Id \"\"", "proxy_set_header X-Forwarded-For \"\"",
        ]
        for directive in required:
            self.assertIn(directive, config)
        agent_location = config[config.index('location ~ "^/agents/'):]
        self.assertNotIn("proxy_pass http://127.0.0.1:18080", agent_location.split("}", 1)[0])

    def test_stateless_fake_streams_multiple_sse_chunks(self) -> None:
        status, headers, chunks = asyncio.run(call(StatelessFakeAgent(), path="/events"))
        self.assertEqual(200, status)
        self.assertEqual("text/event-stream", headers["content-type"])
        self.assertGreaterEqual(len([chunk for chunk in chunks if chunk]), 2)
        self.assertIn(b"event: complete", b"".join(chunks))

    def test_identity_fake_reads_only_gateway_injected_identity(self) -> None:
        agent = IdentityAwareFakeAgent(lambda token, *, audience: {"userId": "user-a", "agentId": audience})
        self.assertEqual(401, asyncio.run(call(agent))[0])
        status, _, chunks = asyncio.run(call(agent, headers={"x-genb-identity-token": "signed"}))
        self.assertEqual(200, status)
        self.assertEqual({"userId": "user-a", "agentId": "identity-agent"}, json.loads(b"".join(chunks)))


if __name__ == "__main__":
    unittest.main()
