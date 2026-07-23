import json
from pathlib import Path

from control_system.app import create_app
from control_system.identity import StaticIdentityVerifier
from control_system.short_term_memory.store import InMemorySessionStore


def test_committed_openapi_matches_the_public_interface() -> None:
    app = create_app(
        identity_verifier=StaticIdentityVerifier(credentials={}),
        session_store=InMemorySessionStore(),
    )
    contract_path = (
        Path(__file__).parents[2] / "openapi" / "control-system-v1.json"
    )
    committed = json.loads(contract_path.read_text(encoding="utf-8"))

    assert committed == app.openapi()
    assert committed["components"]["securitySchemes"] == {
        "ActorToken": {
            "type": "apiKey",
            "description": "GenB-issued signed Actor Token",
            "in": "header",
            "name": "X-GenB-Actor-Token",
        },
        "ServiceCredential": {
            "type": "http",
            "description": "GenB-issued service credential",
            "scheme": "bearer",
        },
    }
    assert {
        "/api/v1/control-system/short-term-memory/turns:commit",
        "/api/v1/control-system/short-term-memory/context:prepare",
        "/api/v1/control-system/short-term-memory/sessions/{sessionId}",
    }.issubset(committed["paths"])
