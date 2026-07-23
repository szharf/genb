from fastapi.testclient import TestClient

from control_system.app import create_app
from control_system.identity import StaticIdentityVerifier
from control_system.long_term_memory.repository import InMemoryLongTermMemoryRepository
from control_system.short_term_memory.store import InMemorySessionStore
from control_system.summary import UnavailableSummaryGenerator


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
        "dependencies": {"shortTermStore": "UP", "longTermStore": "UP"},
    }
    assert version.status_code == 200
    assert version.json() == {
        "service": "control-system-service",
        "version": "0.2.0",
        "interfaceVersion": "1.0.0",
    }


def test_runtime_inference_failure_is_reported_as_degraded_not_fake_success() -> None:
    app = create_app(
        identity_verifier=StaticIdentityVerifier(credentials={}),
        session_store=InMemorySessionStore(),
        summary_generator=UnavailableSummaryGenerator(),
    )

    with TestClient(app) as client:
        ready = client.get("/health/ready")

    assert ready.status_code == 200
    assert ready.json()["status"] == "UP"
    assert ready.json()["degradedDependencies"] == ["runtime-inference"]


class UnavailableLongTermRepository(InMemoryLongTermMemoryRepository):
    async def health(self) -> bool:
        return False


def test_long_term_store_failure_makes_control_not_ready() -> None:
    app = create_app(
        identity_verifier=StaticIdentityVerifier(credentials={}),
        session_store=InMemorySessionStore(),
        long_term_repository=UnavailableLongTermRepository(),
    )

    with TestClient(app) as client:
        ready = client.get("/health/ready")

    assert ready.status_code == 503
    assert ready.json() == {
        "status": "DOWN",
        "dependencies": {"shortTermStore": "UP", "longTermStore": "DOWN"},
    }
