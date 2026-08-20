from __future__ import annotations

import base64
import hashlib
import hmac
from html import escape
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _token(username: str) -> str:
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({
        "sub": username, "username": username, "iat": now, "exp": now + 300,
    }, separators=(",", ":")).encode())
    signature = _b64(hmac.new(
        os.environ["GENB_LOCAL_JWT_SECRET"].encode(), f"{header}.{payload}".encode(), hashlib.sha256,
    ).digest())
    return f"{header}.{payload}.{signature}"


class Portal(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/authorize":
            return self._authorize(query)
        if parsed.path != "/":
            return self.send_error(404)
        required = {name: query.get(name, [""])[0] for name in ("agentId", "callbackUrl", "state")}
        if not all(required.values()):
            return self.send_error(400)
        buttons = []
        for username in ("admin", "test_user"):
            href = "/authorize?" + urlencode({**required, "as": username})
            buttons.append(f'<a id="login-{username}" href="{escape(href, quote=True)}">{username}</a>')
        body = ("<!doctype html><meta charset=utf-8><title>M5 Local Portal</title>"
                "<h1>M5 本地统一身份夹具</h1><p>身份由真实 GenB authorize Interface 签发。</p>"
                + " ".join(buttons)).encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def _authorize(self, query: dict[str, list[str]]) -> None:
        values = {name: query.get(name, [""])[0] for name in ("agentId", "callbackUrl", "state", "as")}
        if values["as"] not in {"admin", "test_user"} or not all(values.values()):
            return self.send_error(400)
        request = Request(
            f'{os.environ["GENB_BASE_URL"].rstrip("/")}/v1/client/agents/{values["agentId"]}/sso/authorize',
            method="POST",
            headers={"Authorization": "Bearer " + _token(values["as"]), "Content-Type": "application/json"},
            data=json.dumps({"callbackUrl": values["callbackUrl"], "state": values["state"]}).encode(),
        )
        try:
            with urlopen(request, timeout=5) as response:
                data = json.loads(response.read())["data"]
        except Exception:
            return self.send_error(502)
        location = data["callbackUrl"] + "?" + urlencode({"code": data["code"], "state": data["state"]})
        self.send_response(303); self.send_header("Location", location); self.end_headers()


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18716), Portal).serve_forever()
