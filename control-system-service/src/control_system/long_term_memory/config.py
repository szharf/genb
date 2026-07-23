import json
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from ..component_config import RuntimeConfigUnavailable
from ..identity import InvocationIdentity

MEMORY_TYPES = frozenset(
    {"USER_PREFERENCE", "STABLE_FACT", "USER_CONSTRAINT"}
)


@dataclass(frozen=True)
class LongTermMemoryRuntimeConfig:
    enabled_types: frozenset[str]
    auto_extraction_enabled: bool
    confidence_threshold: float
    retention_days: int
    top_k: int
    max_top_k: int
    model_alias: str
    max_attempts: int = 3


class LongTermMemoryConfigProvider(Protocol):
    def get(self, identity: InvocationIdentity) -> LongTermMemoryRuntimeConfig: ...


class StaticLongTermMemoryConfigProvider:
    def __init__(self, config: LongTermMemoryRuntimeConfig) -> None:
        self._config = config

    def get(self, identity: InvocationIdentity) -> LongTermMemoryRuntimeConfig:
        del identity
        return self._config


class GenBLongTermMemoryConfigProvider:
    def __init__(
        self,
        *,
        client: httpx.Client,
        config_url_template: str,
        internal_token: str,
        cache_ttl_seconds: float = 30.0,
    ) -> None:
        if len(internal_token) < 16:
            raise ValueError("GenB internal token must contain at least 16 characters")
        self._client = client
        self._url = config_url_template
        self._token = internal_token
        self._cache_ttl = cache_ttl_seconds
        self._cache: dict[int, tuple[float, LongTermMemoryRuntimeConfig]] = {}

    def get(self, identity: InvocationIdentity) -> LongTermMemoryRuntimeConfig:
        config_id = identity.config_version_for("LONG_TERM_MEMORY")
        if config_id is None:
            raise RuntimeConfigUnavailable("Signed binding snapshot has no long-term config")
        cached = self._cache.get(config_id)
        now = time.monotonic()
        if cached and cached[0] > now:
            return cached[1]
        try:
            response = self._client.get(
                self._url.format(config_id=config_id),
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/json",
                },
            )
            if response.status_code != 200 or len(response.content) > 65_536:
                raise RuntimeConfigUnavailable("Published long-term config is unavailable")
            config = _parse(response.json(), config_id)
        except RuntimeConfigUnavailable:
            raise
        except (httpx.HTTPError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeConfigUnavailable("Published long-term config is invalid") from error
        self._cache[config_id] = (now + self._cache_ttl, config)
        return config


def _parse(payload: object, expected_id: int) -> LongTermMemoryRuntimeConfig:
    if not isinstance(payload, dict) or not (
        payload.get("id") == expected_id
        and payload.get("componentCode") == "LONG_TERM_MEMORY"
        and payload.get("status") == "PUBLISHED"
    ):
        raise RuntimeConfigUnavailable("Published long-term config identity is invalid")
    raw = payload.get("config")
    if not isinstance(raw, dict):
        raise RuntimeConfigUnavailable("Published long-term config body is invalid")
    enabled = raw.get("enabledTypes")
    if not (
        isinstance(enabled, list)
        and enabled
        and all(isinstance(value, str) for value in enabled)
        and set(enabled).issubset(MEMORY_TYPES)
    ):
        raise RuntimeConfigUnavailable("enabledTypes is invalid")
    auto = raw.get("autoExtractionEnabled")
    threshold = raw.get("confidenceThreshold")
    retention = raw.get("retentionDays")
    top_k = raw.get("topK")
    max_top_k = raw.get("maxTopK")
    model_alias = raw.get("modelAlias")
    max_attempts = raw.get("maxAttempts", 3)
    if not isinstance(auto, bool):
        raise RuntimeConfigUnavailable("autoExtractionEnabled is invalid")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
        raise RuntimeConfigUnavailable("confidenceThreshold is invalid")
    for name, value, minimum, maximum in (
        ("retentionDays", retention, 1, 3650),
        ("topK", top_k, 1, 50),
        ("maxTopK", max_top_k, 1, 100),
        ("maxAttempts", max_attempts, 1, 10),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise RuntimeConfigUnavailable(f"{name} is invalid")
    if top_k > max_top_k:
        raise RuntimeConfigUnavailable("topK must not exceed maxTopK")
    if not isinstance(model_alias, str) or not model_alias or len(model_alias) > 128:
        raise RuntimeConfigUnavailable("modelAlias is invalid")
    return LongTermMemoryRuntimeConfig(
        enabled_types=frozenset(enabled),
        auto_extraction_enabled=auto,
        confidence_threshold=float(threshold),
        retention_days=retention,
        top_k=top_k,
        max_top_k=max_top_k,
        model_alias=model_alias,
        max_attempts=max_attempts,
    )
