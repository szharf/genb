import json
import os
from pathlib import Path

from fastapi import FastAPI
from redis.asyncio import Redis

from .app import create_app
from .identity import (
    CompositeIdentityVerifier,
    RsaActorTokenVerifier,
    ServiceCredential,
    StaticServiceCredentialIntrospector,
)
from .short_term_memory.redis_store import RedisSessionStore


def create_local_app() -> FastAPI:
    environment = os.getenv("APP_ENV", "local")
    if environment not in {"local", "test"}:
        raise RuntimeError(
            "The local credential adapter is forbidden outside local/test."
        )
    public_key_path = _required_path("CONTROL_SYSTEM_ACTOR_PUBLIC_KEY_PATH")
    credentials_path = _required_path("CONTROL_SYSTEM_LOCAL_CREDENTIALS_PATH")
    key_pepper = _required("REDIS_KEY_PEPPER").encode("utf-8")
    credentials = _load_credentials(credentials_path)
    redis_client = Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD") or None,
        db=int(os.getenv("REDIS_DB", "0")),
        decode_responses=True,
    )
    app = create_app(
        identity_verifier=CompositeIdentityVerifier(
            service_credentials=StaticServiceCredentialIntrospector(
                credentials=credentials
            ),
            actor_tokens=RsaActorTokenVerifier(
                public_key_pem=public_key_path.read_bytes(),
                issuer="genb",
                audience="control-system",
            ),
        ),
        session_store=RedisSessionStore(
            redis_client,
            key_pepper=key_pepper,
        ),
        ttl_seconds=_bounded_int(
            "SHORT_TERM_DEFAULT_TTL_SECONDS", 86400, minimum=60, maximum=2592000
        ),
        max_turns=_bounded_int(
            "SHORT_TERM_MAX_TURNS", 50, minimum=1, maximum=500
        ),
    )
    app.add_event_handler("shutdown", redis_client.aclose)
    return app


def _load_credentials(path: Path) -> dict[str, ServiceCredential]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("Local credential file must be a non-empty array")
    credentials: dict[str, ServiceCredential] = {}
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Local credential entry must be an object")
        token = item.get("token")
        credential_id = item.get("credentialId")
        agent_id = item.get("agentId")
        scopes = item.get("scopes")
        if not (
            isinstance(token, str)
            and token
            and isinstance(credential_id, str)
            and credential_id
            and isinstance(agent_id, str)
            and agent_id
            and isinstance(scopes, list)
            and all(isinstance(scope, str) and scope for scope in scopes)
        ):
            raise ValueError("Local credential entry is invalid")
        if token in credentials:
            raise ValueError("Local credential tokens must be unique")
        credentials[token] = ServiceCredential(
            credential_id=credential_id,
            agent_id=agent_id,
            scopes=frozenset(scopes),
        )
    return credentials


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def _required_path(name: str) -> Path:
    path = Path(_required(name))
    if not path.is_file():
        raise RuntimeError(f"Configured file does not exist: {name}")
    return path


def _bounded_int(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"Environment variable must be an integer: {name}") from error
    if value < minimum or value > maximum:
        raise RuntimeError(
            f"Environment variable is outside the allowed range: {name}"
        )
    return value
