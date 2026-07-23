import base64
import json
from datetime import UTC, datetime, timedelta

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient

from control_system.app import create_app
from control_system.genb_identity import (
    GenBJwksActorTokenVerifier,
    GenBServiceCredentialIntrospector,
)
from control_system.identity import CompositeIdentityVerifier
from control_system.short_term_memory.store import InMemorySessionStore


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unsigned(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return _encode(value.to_bytes(length, "big"))


def _actor_token(private_key: rsa.RSAPrivateKey, *, key_id: str) -> str:
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
        "sessionId": "session-a",
        "components": ["SHORT_TERM_MEMORY"],
    }
    encoded_header = _encode(json.dumps(header).encode())
    encoded_claims = _encode(json.dumps(claims).encode())
    signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{encoded_header}.{encoded_claims}.{_encode(signature)}"


def test_genb_adapters_construct_identity_through_public_memory_interface() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    key_id = "genb-key-a"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/.well-known/jwks.json":
            return httpx.Response(
                200,
                json={
                    "keys": [
                        {
                            "kty": "RSA",
                            "use": "sig",
                            "alg": "RS256",
                            "kid": key_id,
                            "n": _unsigned(public_numbers.n),
                            "e": _unsigned(public_numbers.e),
                        }
                    ]
                },
            )
        if request.url.path == "/api/v1/internal/service-credentials:introspect":
            assert request.headers["authorization"] == "Bearer internal-token-a"
            assert request.headers["x-agent-credential"] == "service-token-a"
            return httpx.Response(
                200,
                json={
                    "active": True,
                    "credentialId": "credential-a",
                    "agentId": "agent-a",
                    "scopes": ["component:short-term-memory:read"],
                    "expiresAt": "2026-12-31T00:00:00",
                    "credentialVersion": 0,
                },
            )
        return httpx.Response(404)

    genb_client = httpx.Client(
        base_url="http://genb.local",
        transport=httpx.MockTransport(handler),
    )
    verifier = CompositeIdentityVerifier(
        service_credentials=GenBServiceCredentialIntrospector(
            client=genb_client,
            introspection_url="/api/v1/internal/service-credentials:introspect",
            internal_token="internal-token-a",
        ),
        actor_tokens=GenBJwksActorTokenVerifier(
            client=genb_client,
            jwks_url="/api/.well-known/jwks.json",
            issuer="genb",
            audience="control-system",
        ),
    )
    app = create_app(
        identity_verifier=verifier,
        session_store=InMemorySessionStore(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers={
                "Authorization": "Bearer service-token-a",
                "X-GenB-Actor-Token": _actor_token(private_key, key_id=key_id),
            },
            json={"query": "hello", "maxContextTokens": 100},
        )

    genb_client.close()
    assert response.status_code == 200
    assert response.json()["data"]["messages"] == []


def test_genb_adapters_fail_closed_for_unknown_key_and_dependency_failure() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("jwks.json"):
            return httpx.Response(200, json={"keys": []})
        return httpx.Response(503)

    genb_client = httpx.Client(transport=httpx.MockTransport(handler))
    credential_introspector = GenBServiceCredentialIntrospector(
        client=genb_client,
        introspection_url="http://genb.local/api/v1/internal/service-credentials:introspect",
        internal_token="internal-token-a",
    )
    actor_verifier = GenBJwksActorTokenVerifier(
        client=genb_client,
        jwks_url="http://genb.local/api/.well-known/jwks.json",
        issuer="genb",
        audience="control-system",
    )

    assert credential_introspector.introspect("service-token-a") is None
    assert actor_verifier.verify(
        _actor_token(private_key, key_id="unknown-key")
    ) is None
    genb_client.close()
