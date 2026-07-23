from dataclasses import replace
from datetime import UTC, datetime

import httpx
import pytest

from control_system.component_config import (
    GenBShortTermMemoryConfigProvider,
    RuntimeConfigUnavailable,
    ShortTermMemoryRuntimeConfig,
    StaticShortTermMemoryConfigProvider,
)
from control_system.identity import InvocationIdentity
from control_system.short_term_memory.models import ConversationTurn
from control_system.short_term_memory.service import ShortTermMemoryService
from control_system.short_term_memory.store import InMemorySessionStore


class RecordingSessionStore(InMemorySessionStore):
    def __init__(self) -> None:
        super().__init__()
        self.last_ttl_seconds: int | None = None

    async def commit(self, *args, ttl_seconds: int, **kwargs):
        self.last_ttl_seconds = ttl_seconds
        return await super().commit(*args, ttl_seconds=ttl_seconds, **kwargs)


def _identity(config_id: int | None = 41) -> InvocationIdentity:
    versions = () if config_id is None else (("SHORT_TERM_MEMORY", config_id),)
    return InvocationIdentity(
        tenant_id="tenant-a",
        user_id="user-a",
        agent_id="agent-a",
        session_id="session-a",
        service_credential_id="credential-a",
        allowed_components=frozenset({"SHORT_TERM_MEMORY"}),
        scopes=frozenset({"component:short-term-memory:read"}),
        request_id="req-config-1",
        component_config_versions=versions,
    )


def test_genb_provider_reads_published_config_by_signed_snapshot_and_caches_version() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        assert request.url.path == "/api/v1/internal/component-configs/41"
        assert request.headers["authorization"] == "Bearer internal-token-a"
        return httpx.Response(
            200,
            json={
                "id": 41,
                "componentCode": "SHORT_TERM_MEMORY",
                "implementationCode": "control-memory-v1",
                "profileCode": "default",
                "versionNumber": 3,
                "config": {
                    "ttlSeconds": 120,
                    "maxTurns": 2,
                    "maxContextTokens": 64,
                },
                "status": "PUBLISHED",
            },
        )

    client = httpx.Client(
        base_url="http://genb.local", transport=httpx.MockTransport(handler)
    )
    provider = GenBShortTermMemoryConfigProvider(
        client=client,
        config_url_template="/api/v1/internal/component-configs/{config_id}",
        internal_token="internal-token-a",
        cache_ttl_seconds=30,
    )

    first = provider.get(_identity())
    second = provider.get(_identity())

    client.close()
    assert first == ShortTermMemoryRuntimeConfig(120, 2, 64)
    assert second == first
    assert request_count == 1


@pytest.mark.parametrize(
    "config_id,response",
    [
        (None, None),
        (41, httpx.Response(503)),
        (41, httpx.Response(200, json={"id": 41, "status": "DRAFT", "config": {}})),
        (
            41,
            httpx.Response(
                200,
                json={
                    "id": 41,
                    "componentCode": "SHORT_TERM_MEMORY",
                    "status": "PUBLISHED",
                    "config": {"ttlSeconds": 1, "maxTurns": 2, "maxContextTokens": 64},
                },
            ),
        ),
    ],
)
def test_genb_provider_fails_closed_for_missing_unavailable_or_invalid_config(
    config_id: int | None, response: httpx.Response | None
) -> None:
    client = httpx.Client(
        base_url="http://genb.local",
        transport=httpx.MockTransport(lambda _request: response or httpx.Response(500)),
    )
    provider = GenBShortTermMemoryConfigProvider(
        client=client,
        config_url_template="/api/v1/internal/component-configs/{config_id}",
        internal_token="internal-token-a",
    )

    with pytest.raises(RuntimeConfigUnavailable):
        provider.get(_identity(config_id))
    client.close()


@pytest.mark.asyncio
async def test_short_term_memory_uses_config_for_ttl_window_and_context_cap() -> None:
    store = RecordingSessionStore()
    memory = ShortTermMemoryService(
        store,
        config_provider=StaticShortTermMemoryConfigProvider(
            ShortTermMemoryRuntimeConfig(
                ttl_seconds=123,
                max_turns=1,
                max_context_tokens=8,
            )
        ),
    )
    identity = replace(
        _identity(),
        scopes=frozenset(
            {
                "component:short-term-memory:read",
                "component:short-term-memory:write",
            }
        ),
    )
    for number in (1, 2):
        await memory.commit_turn(
            identity,
            ConversationTurn(
                turn_id=f"turn-{number}",
                user_message=f"user-{number}",
                assistant_message=f"assistant-{number}",
                occurred_at=datetime(2026, 7, 24, number, tzinfo=UTC),
            ),
            f"idempotency-key-{number}",
        )

    messages, trimmed_count, used_tokens = await memory.prepare_context(
        identity, max_context_tokens=1000
    )

    assert [message.turn_id for message in await store.read(memory._scope(identity))] == [
        "turn-2",
        "turn-2",
    ]
    assert store.last_ttl_seconds == 123
    assert used_tokens <= 8
    assert trimmed_count in {0, 2}
    assert all(message.turn_id == "turn-2" for message in messages)
