import json
import os
from pathlib import Path

from .app import (
    EMBED_SCOPE,
    HEALTH_READ_SCOPE,
    INFER_SCOPE,
    MODELS_READ_SCOPE,
    create_app,
)
from .identity import StaticTokenIdentityVerifier
from .provider import FakeModelProvider
from .routing import build_provider_from_document


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
    routing_config = os.getenv("MODEL_ROUTING_CONFIG")
    provider = None
    if routing_config:
        document = json.loads(
            Path(routing_config).read_text(encoding="utf-8")
        )
        provider = build_provider_from_document(
            document,
            environment=os.environ,
        )
    fake_structured = os.getenv("RUNTIME_FAKE_STRUCTURED_CONTENT")
    if fake_structured:
        if environment == "production":
            raise RuntimeError("RUNTIME_FAKE_STRUCTURED_CONTENT is forbidden in production")
        if len(fake_structured) > 131_072:
            raise RuntimeError("RUNTIME_FAKE_STRUCTURED_CONTENT is too large")
        provider = FakeModelProvider(structured_content=fake_structured)
    return create_app(
        identity_verifier=StaticTokenIdentityVerifier(tokens=tokens),
        provider=provider,
        environment=environment,
    )


app = build_app()
