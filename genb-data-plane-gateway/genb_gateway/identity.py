from __future__ import annotations

import base64
from datetime import timedelta
import json
import secrets
import threading
from typing import Callable

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class IdentityTokens:
    def __init__(self, clock: Callable, ttl: timedelta) -> None:
        self._clock, self._ttl = clock, ttl
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = secrets.token_hex(8)
        self._issued: dict[tuple[str, str, str, str], tuple[str, int]] = {}
        self._lock = threading.RLock()

    def issue(self, session) -> str:
        now = int(self._clock().timestamp())
        cache_key = (session.tenant_id, session.user_id, session.agent_id, session.session_id)
        with self._lock:
            cached = self._issued.get(cache_key)
            if cached is not None and cached[1] > now + 5:
                return cached[0]
            self._issued = {key: value for key, value in self._issued.items() if value[1] > now + 5}
            expires = now + min(60, int(self._ttl.total_seconds()))
            claims = {
                "iss": "genb-data-plane-gateway", "sub": session.user_id, "aud": session.agent_id,
                "iat": now, "exp": expires, "jti": secrets.token_urlsafe(16),
                "tenantId": session.tenant_id, "userId": session.user_id, "agentId": session.agent_id,
                "sessionId": session.session_id,
            }
            header = {"alg": "RS256", "typ": "JWT", "kid": self.kid}
            signing = (f"{_b64(json.dumps(header, separators=(',', ':')).encode())}."
                       f"{_b64(json.dumps(claims, separators=(',', ':')).encode())}")
            signature = self._key.sign(signing.encode(), padding.PKCS1v15(), hashes.SHA256())
            token = f"{signing}.{_b64(signature)}"
            self._issued[cache_key] = token, expires
            return token

    def verify(self, token: str, *, audience: str) -> dict:
        encoded_header, encoded_claims, encoded_signature = token.split(".")
        signing = f"{encoded_header}.{encoded_claims}"
        self._key.public_key().verify(_decode(encoded_signature), signing.encode(), padding.PKCS1v15(), hashes.SHA256())
        claims = json.loads(_decode(encoded_claims))
        if claims["iss"] != "genb-data-plane-gateway" or claims["aud"] != audience or claims["exp"] <= int(self._clock().timestamp()):
            raise ValueError("invalid identity token")
        return claims

    def verify_invocation(self, token: str) -> dict:
        try:
            encoded_claims = token.split(".")[1]
            claimed_audience = json.loads(_decode(encoded_claims))["agentId"]
        except (IndexError, KeyError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("invalid identity token") from error
        return self.verify(token, audience=claimed_audience)

    def jwks(self) -> dict:
        numbers = self._key.public_key().public_numbers()
        return {"keys": [{
            "kty": "RSA", "use": "sig", "alg": "RS256", "kid": self.kid,
            "n": _b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
            "e": _b64(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
        }]}
