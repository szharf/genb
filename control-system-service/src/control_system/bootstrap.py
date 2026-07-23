import json
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis

from .app import create_app
from .component_config import GenBShortTermMemoryConfigProvider
from .long_term_memory.config import GenBLongTermMemoryConfigProvider
from .long_term_memory.extraction import RuntimeInferenceExtractionModel
from .long_term_memory.postgres_repository import PostgreSQLLongTermMemoryRepository
from .identity import (
    CompositeIdentityVerifier,
    RsaActorTokenVerifier,
    ServiceCredential,
    StaticServiceCredentialIntrospector,
)
from .genb_identity import (
    GenBJwksActorTokenVerifier,
    GenBServiceCredentialIntrospector,
)
from .short_term_memory.redis_store import RedisSessionStore
from .summary import RuntimeInferenceSummaryGenerator, UnavailableSummaryGenerator


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


def create_genb_connected_app() -> FastAPI:
    environment = os.getenv("APP_ENV", "local")
    genb_base_url = _required("GENB_BASE_URL").rstrip("/")
    if environment == "production" and urlparse(genb_base_url).scheme != "https":
        raise RuntimeError("GENB_BASE_URL must use HTTPS in production")
    internal_token = _required("CONTROL_SYSTEM_INTERNAL_TOKEN")
    key_pepper = _required("REDIS_KEY_PEPPER").encode("utf-8")
    genb_client = httpx.Client(
        base_url=genb_base_url,
        timeout=httpx.Timeout(
            connect=_bounded_float(
                "GENB_CONNECT_TIMEOUT_SECONDS", 1.0, minimum=0.1, maximum=10.0
            ),
            read=_bounded_float(
                "GENB_READ_TIMEOUT_SECONDS", 2.0, minimum=0.1, maximum=30.0
            ),
            write=2.0,
            pool=1.0,
        ),
    )
    redis_client = _redis_client()
    summary_generator, runtime_client = _runtime_summary_generator(environment)
    postgres_dsn = os.getenv("CONTROL_SYSTEM_POSTGRES_DSN", "")
    if environment == "production" and not postgres_dsn:
        raise RuntimeError("CONTROL_SYSTEM_POSTGRES_DSN is required in production")
    long_term_repository = (
        PostgreSQLLongTermMemoryRepository(postgres_dsn) if postgres_dsn else None
    )
    extraction_model = (
        RuntimeInferenceExtractionModel(
            client=runtime_client,
            service_token=_required("CONTROL_SYSTEM_RUNTIME_TOKEN"),
        )
        if runtime_client is not None
        else None
    )
    app = create_app(
        identity_verifier=CompositeIdentityVerifier(
            service_credentials=GenBServiceCredentialIntrospector(
                client=genb_client,
                introspection_url="/api/v1/internal/service-credentials:introspect",
                internal_token=internal_token,
            ),
            actor_tokens=GenBJwksActorTokenVerifier(
                client=genb_client,
                jwks_url="/api/.well-known/jwks.json",
                issuer="genb",
                audience="control-system",
            ),
        ),
        session_store=RedisSessionStore(
            redis_client,
            key_pepper=key_pepper,
        ),
        config_provider=GenBShortTermMemoryConfigProvider(
            client=genb_client,
            config_url_template="/api/v1/internal/component-configs/{config_id}",
            internal_token=internal_token,
            cache_ttl_seconds=_bounded_float(
                "GENB_CONFIG_CACHE_TTL_SECONDS", 30.0, minimum=1.0, maximum=3600.0
            ),
        ),
        summary_generator=summary_generator,
        long_term_repository=long_term_repository,
        long_term_config_provider=GenBLongTermMemoryConfigProvider(
            client=genb_client,
            config_url_template="/api/v1/internal/component-configs/{config_id}",
            internal_token=internal_token,
            cache_ttl_seconds=_bounded_float(
                "GENB_CONFIG_CACHE_TTL_SECONDS", 30.0, minimum=1.0, maximum=3600.0
            ),
        ),
        extraction_model=extraction_model,
        run_extraction_worker=long_term_repository is not None,
        extraction_worker_poll_seconds=_bounded_float(
            "LONG_TERM_WORKER_POLL_SECONDS", 1.0, minimum=0.1, maximum=60.0
        ),
    )
    app.add_event_handler("shutdown", redis_client.aclose)
    app.add_event_handler("shutdown", genb_client.close)
    if runtime_client is not None:
        app.add_event_handler("shutdown", runtime_client.aclose)
    if long_term_repository is not None:
        app.add_event_handler("shutdown", long_term_repository.close)
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


def _bounded_float(
    name: str,
    default: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"Environment variable must be numeric: {name}") from error
    if value < minimum or value > maximum:
        raise RuntimeError(
            f"Environment variable is outside the allowed range: {name}"
        )
    return value


def _redis_client() -> Redis:
    return Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD") or None,
        db=int(os.getenv("REDIS_DB", "0")),
        decode_responses=True,
    )


def _runtime_summary_generator(
    environment: str,
) -> tuple[RuntimeInferenceSummaryGenerator | UnavailableSummaryGenerator, httpx.AsyncClient | None]:
    base_url = os.getenv("RUNTIME_INFERENCE_BASE_URL", "").rstrip("/")
    service_token = os.getenv("CONTROL_SYSTEM_RUNTIME_TOKEN", "")
    if bool(base_url) != bool(service_token):
        raise RuntimeError(
            "RUNTIME_INFERENCE_BASE_URL and CONTROL_SYSTEM_RUNTIME_TOKEN must be configured together"
        )
    if not base_url:
        if environment == "production":
            raise RuntimeError("Runtime Inference summary adapter is required in production")
        return UnavailableSummaryGenerator(), None
    if environment == "production" and urlparse(base_url).scheme != "https":
        raise RuntimeError("RUNTIME_INFERENCE_BASE_URL must use HTTPS in production")
    client = httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(
            connect=_bounded_float(
                "RUNTIME_CONNECT_TIMEOUT_SECONDS", 3.0, minimum=0.1, maximum=10.0
            ),
            read=_bounded_float(
                "RUNTIME_READ_TIMEOUT_SECONDS", 30.0, minimum=1.0, maximum=60.0
            ),
            write=5.0,
            pool=2.0,
        ),
    )
    return (
        RuntimeInferenceSummaryGenerator(
            client=client,
            service_token=service_token,
        ),
        client,
    )
