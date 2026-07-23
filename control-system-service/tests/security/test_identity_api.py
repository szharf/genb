import base64
import json
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient

from control_system.app import create_app
from control_system.identity import (
    CompositeIdentityVerifier,
    RsaActorTokenVerifier,
    ServiceCredential,
    StaticServiceCredentialIntrospector,
)
from control_system.short_term_memory.store import InMemorySessionStore


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _actor_token(private_key: rsa.RSAPrivateKey, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "iss": "genb",
        "aud": "control-system",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "nbf": int((now - timedelta(seconds=5)).timestamp()),
        "tenantId": "tenant-a",
        "userId": "user-a",
        "agentId": "agent-a",
        "sessionId": "session-a",
        "components": ["SHORT_TERM_MEMORY"],
    }
    claims.update(overrides)
    encoded_header = _encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    encoded_claims = _encode(json.dumps(claims).encode())
    signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{encoded_header}.{encoded_claims}.{_encode(signature)}"


def test_valid_service_credential_and_signed_actor_token_create_identity() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    identity_verifier = CompositeIdentityVerifier(
        service_credentials=StaticServiceCredentialIntrospector(
            credentials={
                "service-token-a": ServiceCredential(
                    credential_id="credential-a",
                    agent_id="agent-a",
                    scopes=frozenset({"short-term:read"}),
                )
            }
        ),
        actor_tokens=RsaActorTokenVerifier(
            public_key_pem=public_key_pem,
            issuer="genb",
            audience="control-system",
        ),
    )
    app = create_app(
        identity_verifier=identity_verifier,
        session_store=InMemorySessionStore(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers={
                "Authorization": "Bearer service-token-a",
                "X-GenB-Actor-Token": _actor_token(private_key),
                "X-Request-Id": "req-rsa-identity",
            },
            json={"query": "hello", "maxContextTokens": 100},
        )

    assert response.status_code == 200
    assert response.json()["data"]["messages"] == []
    assert response.json()["meta"]["requestId"] == "req-rsa-identity"


def test_service_credential_and_actor_token_agent_mismatch_is_denied() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    app = create_app(
        identity_verifier=CompositeIdentityVerifier(
            service_credentials=StaticServiceCredentialIntrospector(
                credentials={
                    "service-token-a": ServiceCredential(
                        credential_id="credential-a",
                        agent_id="agent-a",
                        scopes=frozenset({"short-term:read"}),
                    )
                }
            ),
            actor_tokens=RsaActorTokenVerifier(
                public_key_pem=public_key_pem,
                issuer="genb",
                audience="control-system",
            ),
        ),
        session_store=InMemorySessionStore(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers={
                "Authorization": "Bearer service-token-a",
                "X-GenB-Actor-Token": _actor_token(
                    private_key, agentId="agent-other"
                ),
                "X-Request-Id": "req-agent-mismatch",
            },
            json={"query": "hello", "maxContextTokens": 100},
        )

    assert response.status_code == 403
    assert response.json()["code"] == "CONTROL_SCOPE_DENIED"
    assert "agent-a" not in response.text
    assert "agent-other" not in response.text


def test_expired_actor_token_is_unauthenticated() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    app = create_app(
        identity_verifier=CompositeIdentityVerifier(
            service_credentials=StaticServiceCredentialIntrospector(
                credentials={
                    "service-token-a": ServiceCredential(
                        credential_id="credential-a",
                        agent_id="agent-a",
                        scopes=frozenset({"short-term:read"}),
                    )
                }
            ),
            actor_tokens=RsaActorTokenVerifier(
                public_key_pem=public_key_pem,
                issuer="genb",
                audience="control-system",
            ),
        ),
        session_store=InMemorySessionStore(),
    )
    expired_at = int((datetime.now(UTC) - timedelta(minutes=5)).timestamp())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers={
                "Authorization": "Bearer service-token-a",
                "X-GenB-Actor-Token": _actor_token(private_key, exp=expired_at),
                "X-Request-Id": "req-expired-actor",
            },
            json={"query": "hello", "maxContextTokens": 100},
        )

    assert response.status_code == 401
    assert response.json()["code"] == "CONTROL_CALLER_UNAUTHENTICATED"
