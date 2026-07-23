import json
from pathlib import Path

from control_system.app import create_app
from control_system.identity import StaticIdentityVerifier
from control_system.short_term_memory.store import InMemorySessionStore


def main() -> None:
    app = create_app(
        identity_verifier=StaticIdentityVerifier(credentials={}),
        session_store=InMemorySessionStore(),
    )
    output = Path(__file__).parents[1] / "openapi" / "control-system-v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
