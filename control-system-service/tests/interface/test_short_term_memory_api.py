from dataclasses import replace
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from control_system.app import create_app
from control_system.identity import InvocationIdentity, StaticIdentityVerifier
from control_system.short_term_memory.store import (
    InMemorySessionStore,
    StoreUnavailableError,
)


def test_caller_can_commit_a_turn_and_prepare_the_same_session_context() -> None:
    identity = InvocationIdentity(
        tenant_id="tenant-a",
        user_id="user-a",
        agent_id="agent-a",
        session_id="session-a",
        service_credential_id="credential-a",
        allowed_components=frozenset({"SHORT_TERM_MEMORY"}),
        scopes=frozenset({"short-term:read", "short-term:write"}),
        request_id="fixture-request",
    )
    app = create_app(
        identity_verifier=StaticIdentityVerifier(
            credentials={("service-token-a", "actor-token-a"): identity}
        ),
        session_store=InMemorySessionStore(),
    )

    with TestClient(app) as client:
        commit_response = client.post(
            "/api/v1/control-system/short-term-memory/turns:commit",
            headers={
                "Authorization": "Bearer service-token-a",
                "X-GenB-Actor-Token": "actor-token-a",
                "X-Request-Id": "req-commit-001",
                "Idempotency-Key": "idem-commit-0001",
            },
            json={
                "turnId": "turn-0001",
                "userMessage": "我偏好低风险产品",
                "assistantMessage": "已记住你的风险偏好。",
                "occurredAt": datetime(2026, 7, 23, 10, 0, tzinfo=UTC).isoformat(),
            },
        )
        prepare_response = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers={
                "Authorization": "Bearer service-token-a",
                "X-GenB-Actor-Token": "actor-token-a",
                "X-Request-Id": "req-prepare-001",
            },
            json={"query": "我的偏好是什么？", "maxContextTokens": 1000},
        )

    assert commit_response.status_code == 200
    assert commit_response.json()["data"] == {
        "turnId": "turn-0001",
        "duplicate": False,
        "messageCount": 2,
    }
    assert commit_response.json()["meta"]["requestId"] == "req-commit-001"
    assert prepare_response.status_code == 200
    assert [
        (message["role"], message["content"])
        for message in prepare_response.json()["data"]["messages"]
    ] == [
        ("user", "我偏好低风险产品"),
        ("assistant", "已记住你的风险偏好。"),
    ]
    assert prepare_response.json()["meta"] == {
        "requestId": "req-prepare-001",
        "componentCode": "SHORT_TERM_MEMORY",
        "implementationCode": "control-memory-v1",
        "interfaceVersion": "1.0.0",
        "estimatedTokens": True,
        "estimatedTokenCount": 18,
        "trimmedMessageCount": 0,
    }


def test_short_term_memory_requires_both_credentials() -> None:
    app = create_app(
        identity_verifier=StaticIdentityVerifier(credentials={}),
        session_store=InMemorySessionStore(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers={
                "Authorization": "Bearer service-token-only",
                "X-Request-Id": "req-missing-actor",
            },
            json={"query": "hello", "maxContextTokens": 100},
        )

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "CONTROL_CALLER_UNAUTHENTICATED"
    assert response.json()["requestId"] == "req-missing-actor"


def test_same_idempotency_key_rejects_a_different_turn() -> None:
    identity = InvocationIdentity(
        tenant_id="tenant-a",
        user_id="user-a",
        agent_id="agent-a",
        session_id="session-a",
        service_credential_id="credential-a",
        allowed_components=frozenset({"SHORT_TERM_MEMORY"}),
        scopes=frozenset({"short-term:write"}),
        request_id="fixture-request",
    )
    app = create_app(
        identity_verifier=StaticIdentityVerifier(
            credentials={("service-token-a", "actor-token-a"): identity}
        ),
        session_store=InMemorySessionStore(),
    )
    headers = {
        "Authorization": "Bearer service-token-a",
        "X-GenB-Actor-Token": "actor-token-a",
        "X-Request-Id": "req-idempotency-conflict",
        "Idempotency-Key": "idem-conflict-0001",
    }
    first_turn = {
        "turnId": "turn-0001",
        "userMessage": "first",
        "assistantMessage": "answer one",
        "occurredAt": "2026-07-23T10:00:00Z",
    }

    with TestClient(app) as client:
        first_response = client.post(
            "/api/v1/control-system/short-term-memory/turns:commit",
            headers=headers,
            json=first_turn,
        )
        conflict_response = client.post(
            "/api/v1/control-system/short-term-memory/turns:commit",
            headers=headers,
            json={
                **first_turn,
                "turnId": "turn-0002",
                "userMessage": "payload-must-not-be-echoed",
            },
        )

    assert first_response.status_code == 200
    assert conflict_response.status_code == 409
    assert conflict_response.json()["code"] == "SHORT_TERM_IDEMPOTENCY_CONFLICT"
    assert "payload-must-not-be-echoed" not in conflict_response.text


def test_clear_session_is_idempotent_and_only_clears_the_signed_session() -> None:
    store = InMemorySessionStore()
    identity_a = InvocationIdentity(
        tenant_id="tenant-a",
        user_id="user-a",
        agent_id="agent-a",
        session_id="session-a",
        service_credential_id="credential-a",
        allowed_components=frozenset({"SHORT_TERM_MEMORY"}),
        scopes=frozenset(
            {"short-term:read", "short-term:write", "short-term:delete"}
        ),
        request_id="fixture-a",
    )
    identity_b = InvocationIdentity(
        **{
            **identity_a.__dict__,
            "session_id": "session-b",
            "request_id": "fixture-b",
        }
    )
    app = create_app(
        identity_verifier=StaticIdentityVerifier(
            credentials={
                ("service-a", "actor-a"): identity_a,
                ("service-a", "actor-b"): identity_b,
            }
        ),
        session_store=store,
    )

    def headers(actor_token: str, request_id: str) -> dict[str, str]:
        return {
            "Authorization": "Bearer service-a",
            "X-GenB-Actor-Token": actor_token,
            "X-Request-Id": request_id,
            "Idempotency-Key": f"idem-{request_id}-0000",
        }

    turn = {
        "turnId": "turn-1",
        "userMessage": "hello",
        "assistantMessage": "world",
        "occurredAt": "2026-07-23T10:00:00Z",
    }
    with TestClient(app) as client:
        for actor, request_id in [("actor-a", "session-a"), ("actor-b", "session-b")]:
            response = client.post(
                "/api/v1/control-system/short-term-memory/turns:commit",
                headers=headers(actor, request_id),
                json=turn,
            )
            assert response.status_code == 200

        first_clear = client.delete(
            "/api/v1/control-system/short-term-memory/sessions/session-a",
            headers=headers("actor-a", "clear-session-a"),
        )
        second_clear = client.delete(
            "/api/v1/control-system/short-term-memory/sessions/session-a",
            headers=headers("actor-a", "clear-session-a-again"),
        )
        session_b = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers=headers("actor-b", "prepare-session-b"),
            json={"query": "hello", "maxContextTokens": 100},
        )

    assert first_clear.status_code == 200
    assert first_clear.json()["data"] == {"cleared": True}
    assert second_clear.status_code == 200
    assert second_clear.json()["data"] == {"cleared": False}
    assert len(session_b.json()["data"]["messages"]) == 2


def test_commit_redacts_passwords_before_they_are_retrievable() -> None:
    identity = InvocationIdentity(
        tenant_id="tenant-a",
        user_id="user-a",
        agent_id="agent-a",
        session_id="session-secret",
        service_credential_id="credential-a",
        allowed_components=frozenset({"SHORT_TERM_MEMORY"}),
        scopes=frozenset({"short-term:read", "short-term:write"}),
        request_id="fixture-request",
    )
    app = create_app(
        identity_verifier=StaticIdentityVerifier(
            credentials={("service-token-a", "actor-token-a"): identity}
        ),
        session_store=InMemorySessionStore(),
    )

    with TestClient(app) as client:
        commit = client.post(
            "/api/v1/control-system/short-term-memory/turns:commit",
            headers={
                "Authorization": "Bearer service-token-a",
                "X-GenB-Actor-Token": "actor-token-a",
                "X-Request-Id": "req-secret-commit",
                "Idempotency-Key": "idem-secret-commit-0001",
            },
            json={
                "turnId": "turn-secret",
                "userMessage": "password=super-secret-value",
                "assistantMessage": "Bearer fake-token-value",
                "occurredAt": "2026-07-23T10:00:00Z",
            },
        )
        prepared = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers={
                "Authorization": "Bearer service-token-a",
                "X-GenB-Actor-Token": "actor-token-a",
                "X-Request-Id": "req-secret-prepare",
            },
            json={"query": "hello", "maxContextTokens": 100},
        )

    assert commit.status_code == 200
    assert prepared.status_code == 200
    assert "super-secret-value" not in prepared.text
    assert "fake-token-value" not in prepared.text
    assert prepared.text.count("[REDACTED]") == 2


def test_prepare_is_isolated_by_tenant_user_agent_and_session() -> None:
    origin = InvocationIdentity(
        tenant_id="tenant-a",
        user_id="user-a",
        agent_id="agent-a",
        session_id="session-a",
        service_credential_id="credential-a",
        allowed_components=frozenset({"SHORT_TERM_MEMORY"}),
        scopes=frozenset({"short-term:read", "short-term:write"}),
        request_id="fixture-origin",
    )
    identities = {
        "origin": origin,
        "tenant": replace(origin, tenant_id="tenant-b"),
        "user": replace(origin, user_id="user-b"),
        "agent": replace(origin, agent_id="agent-b"),
        "session": replace(origin, session_id="session-b"),
    }
    app = create_app(
        identity_verifier=StaticIdentityVerifier(
            credentials={
                (f"service-{name}", f"actor-{name}"): identity
                for name, identity in identities.items()
            }
        ),
        session_store=InMemorySessionStore(),
    )

    with TestClient(app) as client:
        committed = client.post(
            "/api/v1/control-system/short-term-memory/turns:commit",
            headers={
                "Authorization": "Bearer service-origin",
                "X-GenB-Actor-Token": "actor-origin",
                "X-Request-Id": "req-isolation-commit",
                "Idempotency-Key": "idem-isolation-commit-0001",
            },
            json={
                "turnId": "turn-isolation",
                "userMessage": "visible only in the origin scope",
                "assistantMessage": "acknowledged",
                "occurredAt": "2026-07-23T10:00:00Z",
            },
        )
        isolated_results = []
        for name in ("tenant", "user", "agent", "session"):
            response = client.post(
                "/api/v1/control-system/short-term-memory/context:prepare",
                headers={
                    "Authorization": f"Bearer service-{name}",
                    "X-GenB-Actor-Token": f"actor-{name}",
                    "X-Request-Id": f"req-isolation-{name}",
                },
                json={"query": "hello", "maxContextTokens": 100},
            )
            isolated_results.append(response)

    assert committed.status_code == 200
    assert all(response.status_code == 200 for response in isolated_results)
    assert all(response.json()["data"]["messages"] == [] for response in isolated_results)


def test_prepare_keeps_the_latest_messages_within_the_requested_budget() -> None:
    identity = InvocationIdentity(
        tenant_id="tenant-a",
        user_id="user-a",
        agent_id="agent-a",
        session_id="session-budget",
        service_credential_id="credential-a",
        allowed_components=frozenset({"SHORT_TERM_MEMORY"}),
        scopes=frozenset({"short-term:read", "short-term:write"}),
        request_id="fixture-budget",
    )
    app = create_app(
        identity_verifier=StaticIdentityVerifier(
            credentials={("service-a", "actor-a"): identity}
        ),
        session_store=InMemorySessionStore(),
    )
    headers = {
        "Authorization": "Bearer service-a",
        "X-GenB-Actor-Token": "actor-a",
        "X-Request-Id": "req-budget",
    }

    with TestClient(app) as client:
        for number in (1, 2):
            response = client.post(
                "/api/v1/control-system/short-term-memory/turns:commit",
                headers={
                    **headers,
                    "Idempotency-Key": f"idem-budget-turn-{number:04d}",
                },
                json={
                    "turnId": f"turn-{number}",
                    "userMessage": f"user-{number}-abcdefghij",
                    "assistantMessage": f"answer-{number}-abcdefg",
                    "occurredAt": f"2026-07-23T10:0{number}:00Z",
                },
            )
            assert response.status_code == 200
        prepared = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers=headers,
            json={"query": "latest", "maxContextTokens": 12},
        )

    assert [message["turnId"] for message in prepared.json()["data"]["messages"]] == [
        "turn-2",
        "turn-2",
    ]
    assert prepared.json()["meta"]["estimatedTokenCount"] <= 12
    assert prepared.json()["meta"]["trimmedMessageCount"] == 2


def test_store_failure_returns_dependency_problem_without_internal_details() -> None:
    class UnavailableStore(InMemorySessionStore):
        async def read(self, scope):
            del scope
            raise StoreUnavailableError("redis://user:password@internal-host")

    identity = InvocationIdentity(
        tenant_id="tenant-a",
        user_id="user-a",
        agent_id="agent-a",
        session_id="session-a",
        service_credential_id="credential-a",
        allowed_components=frozenset({"SHORT_TERM_MEMORY"}),
        scopes=frozenset({"short-term:read"}),
        request_id="fixture-failure",
    )
    app = create_app(
        identity_verifier=StaticIdentityVerifier(
            credentials={("service-a", "actor-a"): identity}
        ),
        session_store=UnavailableStore(),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/control-system/short-term-memory/context:prepare",
            headers={
                "Authorization": "Bearer service-a",
                "X-GenB-Actor-Token": "actor-a",
                "X-Request-Id": "req-store-down",
            },
            json={"query": "hello", "maxContextTokens": 100},
        )

    assert response.status_code == 503
    assert response.json()["code"] == "SHORT_TERM_STORE_UNAVAILABLE"
    assert "password" not in response.text
    assert "internal-host" not in response.text
