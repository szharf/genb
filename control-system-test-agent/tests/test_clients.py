import json

import httpx
import pytest

from control_system_test_agent.clients import ControlSystemClient, GenBClient
from control_system_test_agent.errors import RemoteCallError


@pytest.mark.asyncio
async def test_genb_client_exchanges_user_and_agent_credentials_for_actor_token() -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["Authorization"]
        seen["credential"] = request.headers["X-Agent-Credential"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "data": {
                    "componentSessionId": "component-session-a",
                    "actorToken": "actor-token-a",
                    "expiresAt": "2026-07-23T12:00:00Z",
                    "components": [
                        {
                            "componentCode": "SHORT_TERM_MEMORY",
                            "implementationCode": "control-memory-v1",
                            "baseUrl": "http://control-system:8701",
                            "interfaceVersion": "1.0.0",
                            "configVersionId": 7,
                            "scopes": [
                                "component:short-term-memory:read",
                                "component:short-term-memory:write",
                            ],
                        }
                    ],
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        session = await GenBClient(http, "http://genb.local/api").issue_component_session(
            user_token="user-token-a",
            service_credential="service-secret-a",
            agent_id="memory-test-a",
            session_id="chat-session-a",
            requested_components=("SHORT_TERM_MEMORY",),
        )

    assert seen == {
        "url": "http://genb.local/api/v1/client/agents/memory-test-a/component-session",
        "authorization": "Bearer user-token-a",
        "credential": "service-secret-a",
        "body": {
            "sessionId": "chat-session-a",
            "requestedComponents": ["SHORT_TERM_MEMORY"],
        },
    }
    assert session.actor_token == "actor-token-a"
    assert session.components[0].config_version_id == 7


@pytest.mark.asyncio
async def test_control_client_sends_both_credentials_and_request_ids() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("context:prepare"):
            return httpx.Response(
                200,
                json={
                    "data": {"messages": [{"role": "user", "content": "remember me"}]},
                    "meta": {"requestId": "req-prepare"},
                },
            )
        return httpx.Response(
            200,
            json={"data": {"turnId": "turn-a", "duplicate": False, "messageCount": 2}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ControlSystemClient(http, "http://control.local")
        prepared = await client.prepare_context(
            service_credential="service-secret-a",
            actor_token="actor-token-a",
            query="what do you remember?",
            max_context_tokens=800,
            request_id="req-prepare",
        )
        committed = await client.commit_turn(
            service_credential="service-secret-a",
            actor_token="actor-token-a",
            turn_id="turn-a",
            user_message="hello",
            assistant_message="world",
            occurred_at="2026-07-23T10:00:00Z",
            request_id="req-commit",
            idempotency_key="idem-memory-test-0001",
        )

    assert prepared.messages[0].content == "remember me"
    assert committed.message_count == 2
    assert requests[0].headers["Authorization"] == "Bearer service-secret-a"
    assert requests[0].headers["X-GenB-Actor-Token"] == "actor-token-a"
    assert requests[1].headers["Idempotency-Key"] == "idem-memory-test-0001"


@pytest.mark.asyncio
async def test_remote_error_does_not_expose_credentials_or_response_body() -> None:
    secret = "service-secret-must-never-leak"
    actor = "actor-token-must-never-leak"

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text=f"upstream echoed {secret} {actor}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ControlSystemClient(http, "http://control.local")
        with pytest.raises(RemoteCallError) as caught:
            await client.prepare_context(
                service_credential=secret,
                actor_token=actor,
                query="private query",
                max_context_tokens=100,
                request_id="req-denied",
            )

    rendered = repr(caught.value) + str(caught.value)
    assert caught.value.status_code == 403
    assert secret not in rendered
    assert actor not in rendered
    assert "private query" not in rendered
    assert "upstream echoed" not in rendered


@pytest.mark.asyncio
async def test_network_timeout_is_mapped_without_exposing_request_data() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout with private transport detail", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = GenBClient(http, "http://genb.local/api")
        with pytest.raises(RemoteCallError) as caught:
            await client.issue_component_session(
                user_token="user-token-private",
                service_credential="service-secret-private",
                agent_id="memory-test-a",
                session_id="private-session",
                requested_components=("SHORT_TERM_MEMORY",),
            )

    rendered = repr(caught.value) + str(caught.value)
    assert caught.value.status_code is None
    assert "service-secret-private" not in rendered
    assert "user-token-private" not in rendered
    assert "private-session" not in rendered
    assert "private transport detail" not in rendered


@pytest.mark.asyncio
async def test_long_term_client_supports_extract_status_search_and_soft_delete() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path.endswith("/extractions"):
            return httpx.Response(202, json={"data": {"extractionId": "ext-a", "status": "PENDING"}})
        if path.endswith("/extractions/ext-a"):
            return httpx.Response(200, json={"data": {
                "extractionId": "ext-a", "status": "SUCCEEDED",
                "writtenCount": 1, "rejectedCount": 0,
            }})
        if path.endswith("/search"):
            return httpx.Response(200, json={"data": {"items": [{
                "memoryId": "mem-a", "type": "USER_PREFERENCE",
                "content": "prefers tea", "confidence": 0.95,
            }]}})
        return httpx.Response(200, json={"data": {"deleted": True}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ControlSystemClient(http, "http://control.local")
        extraction_id = await client.request_long_term_extraction(
            service_credential="service-a", actor_token="actor-a", turn_id="turn-a",
            user_message="I prefer tea", assistant_message="noted",
            occurred_at="2026-07-24T00:00:00Z", request_id="req-a",
            idempotency_key="idem-long-term-a",
        )
        status = await client.get_long_term_extraction(
            service_credential="service-a", actor_token="actor-a",
            extraction_id=extraction_id, request_id="req-b",
        )
        items = await client.search_long_term_memory(
            service_credential="service-a", actor_token="actor-a",
            query="tea", request_id="req-c",
        )
        deleted = await client.delete_long_term_memory(
            service_credential="service-a", actor_token="actor-a", memory_id="mem-a",
            reason="acceptance", request_id="req-d",
        )

    assert status.status == "SUCCEEDED" and status.written_count == 1
    assert items[0].memory_type == "USER_PREFERENCE" and deleted is True
    assert requests[0].headers["Idempotency-Key"] == "idem-long-term-a"
    assert all(request.headers["X-GenB-Actor-Token"] == "actor-a" for request in requests)
