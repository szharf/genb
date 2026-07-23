import json

import httpx

from runtime_system.genb_identity import GenBTokenIdentityVerifier


def test_genb_identity_adapter_accepts_only_active_well_formed_credential() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer internal-token-long-enough"
        assert request.headers["X-Agent-Credential"] == "agent-secret"
        return httpx.Response(
            200,
            json={
                "active": True,
                "credentialId": "credential-1",
                "agentId": "agent-1",
                "scopes": ["component:inference-engine:infer"],
                "expiresAt": "2026-08-01T00:00:00Z",
                "credentialVersion": 1,
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://genb.test"
    )
    verifier = GenBTokenIdentityVerifier(
        client=client,
        introspection_url="/api/v1/internal/service-credentials:introspect",
        internal_token="internal-token-long-enough",
    )

    identity = verifier.verify("agent-secret")

    assert identity is not None
    assert identity.token_id == "credential-1"
    assert identity.scopes == frozenset({"component:inference-engine:infer"})


def test_genb_identity_adapter_fails_closed_without_leaking_upstream_payload() -> None:
    responses = [
        httpx.Response(503, text="password=upstream-secret"),
        httpx.Response(200, json={"active": False}),
        httpx.Response(200, content=b"{"),
        httpx.Response(200, content=json.dumps({"active": True}).encode()),
    ]

    for response in responses:
        verifier = GenBTokenIdentityVerifier(
            client=httpx.Client(transport=httpx.MockTransport(lambda _request: response)),
            introspection_url="https://genb.test/api/v1/internal/service-credentials:introspect",
            internal_token="internal-token-long-enough",
        )
        assert verifier.verify("agent-secret") is None


def test_genb_identity_adapter_rejects_short_internal_secret() -> None:
    try:
        GenBTokenIdentityVerifier(
            client=httpx.Client(),
            introspection_url="https://genb.test/introspect",
            internal_token="short",
        )
    except ValueError as error:
        assert "at least 16" in str(error)
    else:
        raise AssertionError("short internal token must be rejected")

