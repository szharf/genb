from fastapi.testclient import TestClient

from control_system.app import create_app
from control_system.identity import StaticIdentityVerifier
from control_system.short_term_memory.store import InMemorySessionStore


def test_control_system_no_longer_publishes_long_term_memory_routes() -> None:
    app = create_app(
        identity_verifier=StaticIdentityVerifier(credentials={}),
        session_store=InMemorySessionStore(),
    )

    with TestClient(app) as client:
        responses = [
            client.post("/api/v1/control-system/long-term-memory/extractions"),
            client.get(
                "/api/v1/control-system/long-term-memory/extractions/retired-job"
            ),
            client.post("/api/v1/control-system/long-term-memory/search"),
            client.post(
                "/api/v1/control-system/long-term-memory/memories/retired-memory:delete"
            ),
        ]

    assert [response.status_code for response in responses] == [404, 404, 404, 404]
    assert all(
        "long-term-memory" not in path for path in app.openapi()["paths"]
    )
