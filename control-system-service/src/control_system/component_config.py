import json
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from .identity import InvocationIdentity


@dataclass(frozen=True)
class ShortTermMemoryRuntimeConfig:
    ttl_seconds: int = 86400
    max_turns: int = 50
    max_context_tokens: int = 64000
    summary_enabled: bool = False
    summary_trigger_turns: int = 20
    summary_model_alias: str = "session-summary-default"


class RuntimeConfigUnavailable(Exception):
    pass


class ShortTermMemoryConfigProvider(Protocol):
    def get(self, identity: InvocationIdentity) -> ShortTermMemoryRuntimeConfig: ...


class StaticShortTermMemoryConfigProvider:
    def __init__(self, config: ShortTermMemoryRuntimeConfig) -> None:
        self._config = config

    def get(self, identity: InvocationIdentity) -> ShortTermMemoryRuntimeConfig:
        del identity
        return self._config


class GenBShortTermMemoryConfigProvider:
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
        if "{config_id}" not in config_url_template:
            raise ValueError("Config URL template must contain {config_id}")
        if not 1 <= cache_ttl_seconds <= 3600:
            raise ValueError("Config cache TTL must be between 1 and 3600 seconds")
        self._client = client
        self._config_url_template = config_url_template
        self._internal_token = internal_token
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[int, tuple[float, ShortTermMemoryRuntimeConfig]] = {}

    def get(self, identity: InvocationIdentity) -> ShortTermMemoryRuntimeConfig:
        config_id = identity.config_version_for("SHORT_TERM_MEMORY")
        if config_id is None:
            raise RuntimeConfigUnavailable("Signed binding snapshot has no runtime config")
        cached = self._cache.get(config_id)
        now = time.monotonic()
        if cached is not None and cached[0] > now:
            return cached[1]
        try:
            response = self._client.get(
                self._config_url_template.format(config_id=config_id),
                headers={
                    "Authorization": f"Bearer {self._internal_token}",
                    "Accept": "application/json",
                },
            )
            if response.status_code != 200 or len(response.content) > 65_536:
                raise RuntimeConfigUnavailable("Published runtime config is unavailable")
            payload = response.json()
            config = _parse_short_term_config(payload, expected_id=config_id)
        except RuntimeConfigUnavailable:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeConfigUnavailable("Published runtime config is invalid") from error
        self._cache[config_id] = (now + self._cache_ttl_seconds, config)
        return config


def _parse_short_term_config(
    payload: object, *, expected_id: int
) -> ShortTermMemoryRuntimeConfig:
    if not isinstance(payload, dict):
        raise RuntimeConfigUnavailable("Published runtime config is invalid")
    if not (
        payload.get("id") == expected_id
        and payload.get("componentCode") == "SHORT_TERM_MEMORY"
        and payload.get("status") == "PUBLISHED"
    ):
        raise RuntimeConfigUnavailable("Published runtime config identity is invalid")
    raw = payload.get("config")
    if not isinstance(raw, dict):
        raise RuntimeConfigUnavailable("Published runtime config body is invalid")
    ttl_seconds = _bounded_int(raw, "ttlSeconds", 60, 2_592_000)
    max_turns = _bounded_int(raw, "maxTurns", 1, 500)
    max_context_tokens = _bounded_int(raw, "maxContextTokens", 1, 64_000)
    return ShortTermMemoryRuntimeConfig(
        ttl_seconds=ttl_seconds,
        max_turns=max_turns,
        max_context_tokens=max_context_tokens,
        summary_enabled=_optional_bool(raw, "summaryEnabled", False),
        summary_trigger_turns=_optional_bounded_int(
            raw, "summaryTriggerTurns", 20, 2, 100
        ),
        summary_model_alias=_optional_string(
            raw, "summaryModelAlias", "session-summary-default", 128
        ),
    )


def _bounded_int(payload: dict[str, object], name: str, minimum: int, maximum: int) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise RuntimeConfigUnavailable(f"Runtime config field is invalid: {name}")
    return value


def _optional_bounded_int(
    payload: dict[str, object], name: str, default: int, minimum: int, maximum: int
) -> int:
    if name not in payload:
        return default
    return _bounded_int(payload, name, minimum, maximum)


def _optional_bool(payload: dict[str, object], name: str, default: bool) -> bool:
    value = payload.get(name, default)
    if not isinstance(value, bool):
        raise RuntimeConfigUnavailable(f"Runtime config field is invalid: {name}")
    return value


def _optional_string(
    payload: dict[str, object], name: str, default: str, maximum: int
) -> str:
    value = payload.get(name, default)
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise RuntimeConfigUnavailable(f"Runtime config field is invalid: {name}")
    return value
