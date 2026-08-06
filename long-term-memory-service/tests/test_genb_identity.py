import base64
import json
from datetime import UTC, datetime, timedelta

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient

import long_term_memory.main as main_module
from long_term_memory.identity import GenBIdentityVerifier


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unsigned(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return _encode(value.to_bytes(length, "big"))


def _actor_token(
    private_key: rsa.RSAPrivateKey,
    key_id: str,
    *,
    scopes: list[str] | None = None,
) -> str:
    now = datetime.now(UTC)
    header = {"kid": key_id, "alg": "RS256"}
    claims = {
        "iss": "genb",
        "aud": ["control-system"],
        "sub": "user-a",
        "iat": int(now.timestamp()),
        "nbf": int((now - timedelta(seconds=5)).timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "tenantId": "tenant-a",
        "userId": "user-a",
        "agentId": "agent-a",
        "sessionId": "conversation-a",
        "tokenType": "COMPONENT_SESSION",
        "components": ["LONG_TERM_MEMORY"],
        "scopes": scopes or ["component:long-term-memory:write"],
    }
    encoded_header = _encode(json.dumps(header).encode())
    encoded_claims = _encode(json.dumps(claims).encode())
    signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{encoded_header}.{encoded_claims}.{_encode(signature)}"


def test_genb_identity_accepts_signed_actor_and_matching_service_credential() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    key_id = "genb-key-a"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/jwks.json"):
            return httpx.Response(
                200,
                json={
                    "keys": [
                        {
                            "kty": "RSA",
                            "alg": "RS256",
                            "kid": key_id,
                            "n": _unsigned(public_numbers.n),
                            "e": _unsigned(public_numbers.e),
                        }
                    ]
                },
            )
        if request.url.path.endswith("/service-credentials:introspect"):
            assert request.headers["authorization"] == "Bearer internal-token-a-123"
            assert request.headers["x-agent-credential"] == "service-token-a"
            return httpx.Response(200, json={"active": True, "agentId": "agent-a"})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    verifier = GenBIdentityVerifier(
        client=client,
        jwks_url="http://genb.local/api/.well-known/jwks.json",
        introspection_url="http://genb.local/api/v1/internal/service-credentials:introspect",
        internal_token="internal-token-a-123",
    )

    identity = verifier.verify(
        service_token="service-token-a",
        actor_token=_actor_token(private_key, key_id),
        required_component="LONG_TERM_MEMORY",
        required_scope="component:long-term-memory:write",
        request_id="req-identity-a",
    )

    client.close()
    assert identity.tenant_id == "tenant-a"
    assert identity.agent_id == "agent-a"
    assert identity.user_id == "user-a"
    assert identity.session_id == "conversation-a"


def test_formal_http_identity_ignores_forged_development_headers(monkeypatch) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(404))
    )
    verifier = GenBIdentityVerifier(
        client=client,
        jwks_url="http://genb.local/api/.well-known/jwks.json",
        introspection_url="http://genb.local/api/v1/internal/service-credentials:introspect",
        internal_token="internal-token-a-123",
    )
    monkeypatch.setattr(main_module, "identity_verifier", verifier)

    with TestClient(main_module.app) as web_client:
        response = web_client.post(
            "/api/v1/long-term-memory/extractions",
            headers={
                "X-Tenant-Id": "forged-tenant",
                "X-Agent-Id": "forged-agent",
                "X-User-Id": "forged-user",
            },
            json={"conversationId": "conversation-a", "messages": []},
        )

    client.close()
    assert response.status_code == 401
    assert response.json() == {"detail": "Actor Token无效"}


def test_formal_search_accepts_long_term_memory_read_scope(monkeypatch) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    key_id = "genb-key-read"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/jwks.json"):
            return httpx.Response(
                200,
                json={
                    "keys": [
                        {
                            "kty": "RSA",
                            "alg": "RS256",
                            "kid": key_id,
                            "n": _unsigned(public_numbers.n),
                            "e": _unsigned(public_numbers.e),
                        }
                    ]
                },
            )
        if request.url.path.endswith("/service-credentials:introspect"):
            return httpx.Response(200, json={"active": True, "agentId": "agent-a"})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    verifier = GenBIdentityVerifier(
        client=client,
        jwks_url="http://genb.local/api/.well-known/jwks.json",
        introspection_url="http://genb.local/api/v1/internal/service-credentials:introspect",
        internal_token="internal-token-a-123",
    )
    monkeypatch.setattr(main_module, "identity_verifier", verifier)

    with TestClient(main_module.app) as web_client:
        response = web_client.post(
            "/api/v1/long-term-memory/memories:search",
            headers={
                "Authorization": "Bearer service-token-a",
                "X-GenB-Actor-Token": _actor_token(
                    private_key,
                    key_id,
                    scopes=["component:long-term-memory:read"],
                ),
            },
            json={"query": "偏好", "sourceTypes": ["CONVERSATION"]},
        )

    client.close()
    assert response.status_code == 200
    assert response.json()["data"]["items"] == []
