import json
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .app import (
    EMBED_SCOPE,
    HEALTH_READ_SCOPE,
    INFER_SCOPE,
    MODELS_READ_SCOPE,
    create_app,
)
from .identity import StaticTokenIdentityVerifier
from .genb_identity import GenBTokenIdentityVerifier
from .provider import FakeModelProvider
from .protection import RuntimeProtectionSettings
from .routing import build_provider_from_document


def build_app():
    environment = os.getenv("APP_ENV", "local").lower()
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
    identity_verifier, identity_client = _identity_verifier(environment)
    app = create_app(
        identity_verifier=identity_verifier,
        provider=provider,
        environment=environment,
        protection_settings=RuntimeProtectionSettings(
            max_input_characters=_bounded_int(
                "RUNTIME_MAX_INPUT_CHARACTERS", 262_144, 1, 4_194_304
            ),
            requests_per_window=_bounded_int(
                "RUNTIME_REQUESTS_PER_WINDOW", 120, 1, 100_000
            ),
            window_seconds=_bounded_int("RUNTIME_RATE_WINDOW_SECONDS", 60, 1, 3600),
            max_concurrent_requests=_bounded_int(
                "RUNTIME_MAX_CONCURRENT_REQUESTS", 32, 1, 10_000
            ),
            acquire_timeout_seconds=_bounded_float(
                "RUNTIME_CAPACITY_WAIT_SECONDS", 0.25, 0.001, 30
            ),
        ),
    )
    if identity_client is not None:
        app.router.add_event_handler("shutdown", identity_client.close)
    return app


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"Environment variable must be an integer: {name}") from error
    if value < minimum or value > maximum:
        raise RuntimeError(f"Environment variable is outside the allowed range: {name}")
    return value


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"Environment variable must be numeric: {name}") from error
    if value < minimum or value > maximum:
        raise RuntimeError(f"Environment variable is outside the allowed range: {name}")
    return value


def _identity_verifier(
    environment: str,
) -> tuple[StaticTokenIdentityVerifier | GenBTokenIdentityVerifier, httpx.Client | None]:
    if environment != "production":
        static_token = os.getenv("RUNTIME_STATIC_TOKEN")
        tokens: dict[str, set[str]] = {}
        if static_token:
            tokens[static_token] = {
                INFER_SCOPE,
                EMBED_SCOPE,
                MODELS_READ_SCOPE,
                HEALTH_READ_SCOPE,
            }
        return StaticTokenIdentityVerifier(tokens=tokens), None
    base_url = _required("GENB_BASE_URL").rstrip("/")
    if urlparse(base_url).scheme != "https":
        raise RuntimeError("GENB_BASE_URL must use HTTPS in production")
    internal_token = _required("COMPONENT_INTROSPECTION_INTERNAL_TOKEN")
    client = httpx.Client(
        base_url=base_url,
        timeout=httpx.Timeout(connect=1.0, read=2.0, write=2.0, pool=1.0),
    )
    return (
        GenBTokenIdentityVerifier(
            client=client,
            introspection_url="/api/v1/internal/service-credentials:introspect",
            internal_token=internal_token,
        ),
        client,
    )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


app = build_app()
