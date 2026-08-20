from __future__ import annotations

import json


async def _start(send, status: int, headers: list[tuple[bytes, bytes]]) -> None:
    await send({"type": "http.response.start", "status": status, "headers": headers})


class StatelessFakeAgent:
    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return
        if scope["path"] == "/events":
            await _start(send, 200, [(b"content-type", b"text/event-stream"), (b"cache-control", b"no-cache")])
            await send({"type": "http.response.body", "body": b"event: message\ndata: first\n\n", "more_body": True})
            await send({"type": "http.response.body", "body": b"event: complete\ndata: done\n\n", "more_body": False})
            return
        if scope["path"] == "/inspect":
            headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
            body = json.dumps({
                "forgedHeaderReceived": "x-genb-forged" in headers,
                "gatewayCookieReceived": "genb_gateway_session" in headers.get("cookie", ""),
                "trustedUserId": headers.get("x-genb-user-id"),
            }, separators=(",", ":")).encode()
            await _start(send, 200, [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())])
            await send({"type": "http.response.body", "body": body})
            return
        body = b'{"agent":"stateless","ok":true}'
        await _start(send, 200, [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())])
        await send({"type": "http.response.body", "body": body})


class IdentityAwareFakeAgent:
    def __init__(self, verify, audience: str = "identity-agent") -> None:
        self._verify = verify
        self._audience = audience

    async def __call__(self, scope, receive, send) -> None:
        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        token = headers.get("x-genb-identity-token")
        if not token:
            return await self._error(send)
        try:
            claims = self._verify(token, audience=self._audience)
        except Exception:
            return await self._error(send)
        body = json.dumps({"userId": claims["userId"], "agentId": claims["agentId"]}, separators=(",", ":")).encode()
        await _start(send, 200, [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())])
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    async def _error(send) -> None:
        body = b'{"code":"INVALID_IDENTITY_TOKEN"}'
        await _start(send, 401, [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())])
        await send({"type": "http.response.body", "body": body})
