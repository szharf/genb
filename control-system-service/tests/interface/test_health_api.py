from fastapi.testclient import TestClient

from control_system.app import create_app
from control_system.identity import StaticIdentityVerifier
from control_system.short_term_memory.store import InMemorySessionStore


def test_live_ready_and_version_expose_no_secrets() -> None:
    app = create_app(
        identity_verifier=StaticIdentityVerifier(credentials={}),
        session_store=InMemorySessionStore(),
    )

    with TestClient(app) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")
        version = client.get("/version")

    assert live.status_code == 200
    assert live.json() == {"status": "UP"}
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "UP",
        "dependencies": {"shortTermStore": "UP"},
    }
    assert version.status_code == 200
    assert version.json() == {
        "service": "control-system-service",
        "version": "0.1.0",
        "interfaceVersion": "1.0.0",
    }
