from __future__ import annotations

import json

import httpx
import pytest

from control_system_test_agent.clients import (
    GatewayBindingClient, GatewayCapabilityClient, GatewayLongTermMemoryClient,
    GatewayPlanningReasoningClient, GatewayShortTermMemoryClient,
)
from control_system_test_agent.orchestrator import DeterministicAnswerer, PlanningTestAgent, StandaloneMemoryTestAgent


@pytest.mark.asyncio
async def test_short_long_and_planning_experiences_use_only_unified_capability_path() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        operation = request.url.path.rsplit("/", 1)[-1].removesuffix(":invoke")
        responses = {
            "prepareShortTermContext": {"data":{"messages":[]}},
            "commitShortTermTurn": {"data":{"messageCount":2,"replayed":False}},
            "createConversationMemoryExtraction": {"data":{"extractionId":"ext-a"}},
            "getLongTermExtraction": {"data":{
                "extractionId":"ext-a", "status":"SUCCEEDED", "writtenCount":1, "rejectedCount":0,
            }},
            "searchLongTermMemories": {"data":{"items":[{
                "memoryId":"mem-a", "type":"USER_PREFERENCE", "content":"prefers tea", "confidence":0.9,
                "sourceType":"CONVERSATION", "sourceRef":"turn-a",
            }]}},
            "analyzeRequirement": {"data":{"status":"CLARIFYING", "questions":[]}},
        }
        return httpx.Response(200, json=responses[operation])

    gateway_url = "http://data-plane.local"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        capability = GatewayCapabilityClient(
            http, gateway_url, identity_token="signed-user-agent-session",
            agent_credential="agent-machine-credential",
        )
        memory_agent = StandaloneMemoryTestAgent(
            agent_id="agent-a", service_credential="agent-machine-credential",
            genb=GatewayBindingClient(gateway_url), memory=GatewayShortTermMemoryClient(capability),
            control=GatewayLongTermMemoryClient(capability), answerer=DeterministicAnswerer(),
        )
        short = await memory_agent.chat(task_id="task-a", session_id="session-a", message="hello",
                                        session_grant="legacy-value-is-not-forwarded")
        stored = await memory_agent.store_long_term(session_id="session-a", message="I prefer tea",
                                                     session_grant="legacy-value-is-not-forwarded")
        recalled = await memory_agent.recall_long_term(session_id="session-b", query="tea",
                                                        session_grant="legacy-value-is-not-forwarded")
        planning = await PlanningTestAgent(
            agent_id="agent-a", service_credential="agent-machine-credential",
            genb=GatewayBindingClient(gateway_url), planning=GatewayPlanningReasoningClient(capability),
        ).invoke(session_id="session-a", operation="ANALYZE", payload={"goal":"build skill"},
                 session_grant="legacy-value-is-not-forwarded")

    assert short.committed is True
    assert stored.status == "SUCCEEDED"
    assert recalled[0].content == "prefers tea"
    assert planning["status"] == "CLARIFYING"
    assert len(requests) == 6
    assert all(request.url.path.startswith("/component-api/v1/capabilities/") for request in requests)
    assert not any("component-session" in request.url.path for request in requests)
    assert all(request.headers["Authorization"] == "Bearer signed-user-agent-session" for request in requests)
    assert all("X-GenB-Actor-Token" not in request.headers for request in requests)
    wire = b"".join(request.content for request in requests)
    assert b"legacy-value-is-not-forwarded" not in wire
    assert all(json.loads(request.content)["schemaVersion"] == "1.0" for request in requests)
