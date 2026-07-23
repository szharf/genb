import os

from .app import (
    EMBED_SCOPE,
    HEALTH_READ_SCOPE,
    INFER_SCOPE,
    MODELS_READ_SCOPE,
    create_app,
)
from .identity import StaticTokenIdentityVerifier


def build_app():
    environment = os.getenv("APP_ENV", "local").lower()
    static_token = os.getenv("RUNTIME_STATIC_TOKEN")
    tokens: dict[str, set[str]] = {}
    if static_token and environment != "production":
        tokens[static_token] = {
            INFER_SCOPE,
            EMBED_SCOPE,
            MODELS_READ_SCOPE,
            HEALTH_READ_SCOPE,
        }
    return create_app(
        identity_verifier=StaticTokenIdentityVerifier(tokens=tokens),
        environment=environment,
    )


app = build_app()
