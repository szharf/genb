from __future__ import annotations

import json
import unittest

from genb_gateway.adapters import (
    build_default_adapter_registry, HeterogeneousFakeAdapter, HttpResponse, LongTermMemoryAdapter, PlanningReasoningAdapter,
    ShortTermMemoryAdapter,
)
from genb_gateway.capabilities import AdapterRequest, InvocationSubject, OperationPolicy


class RecordingTransport:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response; self.requests = []
    def send(self, request, timeout_ms: int):
        self.requests.append((request, timeout_ms)); return self.response


def adapter_request(operation: str, *, payload: dict, idempotency_key: str | None = None,
                    upstream: str = "http://127.0.0.1:18705", response_mode: str = "JSON") -> AdapterRequest:
    return AdapterRequest(
        OperationPolicy(operation, 1250, "REQUIRED_KEY" if idempotency_key else "READ", response_mode, 8192),
        InvocationSubject("tenant-1", "user-a", "agent-a", "session-a"), "conversation-a", "request-a",
        payload, upstream, "service-credential", "actor-token", idempotency_key,
    )


class M3AdapterTest(unittest.TestCase):
    def test_default_registry_contains_reviewed_adapters_and_no_dynamic_script(self) -> None:
        registry = build_default_adapter_registry(RecordingTransport(HttpResponse(200, {}, b"{}")))
        for code in ("SHORT_TERM_MEMORY_HTTP", "LONG_TERM_MEMORY_HTTP", "PLANNING_REASONING_HTTP",
                     "RUNTIME_INFERENCE_HTTP", "HETEROGENEOUS_FAKE"):
            self.assertIsNotNone(registry.resolve(code, "1.0.0"))
        self.assertIsNone(registry.resolve("USER_UPLOADED_SCRIPT", "1.0.0"))

    def test_short_term_adapter_maps_commit_to_formal_service_contract(self) -> None:
        transport = RecordingTransport(HttpResponse(200, {"content-type":"application/json"}, b'{"data":{"turnId":"turn-1"}}'))
        adapter = ShortTermMemoryAdapter(transport)
        response = adapter.invoke(adapter_request("commitShortTermTurn", payload={
            "taskId":"task-a","sessionId":"session-a","userMessage":"hello","assistantMessage":"hi"
        }, idempotency_key="turn-001"))
        request, timeout_ms = transport.requests[0]
        self.assertEqual(("POST", "http://127.0.0.1:18705/api/v1/short-term-memory/turns:commit", 1250),
                         (request.method, request.url, timeout_ms))
        self.assertEqual("Bearer service-credential", request.headers["Authorization"])
        self.assertEqual("actor-token", request.headers["X-GenB-Actor-Token"])
        self.assertEqual("turn-001", request.headers["Idempotency-Key"])
        self.assertNotIn("userId", json.loads(request.body))
        self.assertEqual({"data":{"turnId":"turn-1"}}, json.loads(response.body))

    def test_long_term_adapter_maps_search_without_exposing_gateway_identity(self) -> None:
        transport = RecordingTransport(HttpResponse(200, {"content-type":"application/json"}, b'{"data":{"items":[]}}'))
        response = LongTermMemoryAdapter(transport).invoke(adapter_request(
            "searchLongTermMemories", payload={"query":"tea","sourceTypes":["CONVERSATION"]},
            upstream="http://127.0.0.1:18702",
        ))
        request, _ = transport.requests[0]
        self.assertEqual("http://127.0.0.1:18702/api/v1/long-term-memory/memories:search", request.url)
        self.assertEqual({"query":"tea","sourceTypes":["CONVERSATION"]}, json.loads(request.body))
        self.assertNotIn("X-GenB-Identity-Token", request.headers)
        self.assertEqual([], json.loads(response.body)["data"]["items"])

    def test_long_term_status_path_is_derived_only_from_valid_payload_identifier(self) -> None:
        transport = RecordingTransport(HttpResponse(200, {"content-type":"application/json"}, b'{"data":{"status":"SUCCEEDED"}}'))
        adapter = LongTermMemoryAdapter(transport)
        response = adapter.invoke(adapter_request(
            "getLongTermExtraction", payload={"extractionId":"ext-a_1"}, upstream="http://long.local",
        ))
        self.assertEqual(200, response.status)
        self.assertEqual("GET", transport.requests[0][0].method)
        self.assertEqual("http://long.local/api/v1/long-term-memory/extractions/ext-a_1", transport.requests[0][0].url)
        with self.assertRaises(LookupError):
            adapter.invoke(adapter_request(
                "getLongTermExtraction", payload={"extractionId":"../admin"}, upstream="http://long.local",
            ))

    def test_planning_adapter_maps_requirement_analysis(self) -> None:
        transport = RecordingTransport(HttpResponse(200, {"content-type":"application/json"},
                                                   b'{"data":{"status":"CLARIFYING","questions":["scope?"]}}'))
        response = PlanningReasoningAdapter(transport).invoke(adapter_request(
            "analyzeRequirement", payload={"goal":"build skill"}, upstream="http://127.0.0.1:18712",
        ))
        request, _ = transport.requests[0]
        self.assertEqual("http://127.0.0.1:18712/api/v1/planning-reasoning/requirements:analyze", request.url)
        self.assertEqual("build skill", json.loads(request.body)["goal"])
        self.assertEqual("CLARIFYING", json.loads(response.body)["data"]["status"])

    def test_json_adapter_preserves_sse_chunks_for_streaming_operation(self) -> None:
        transport = RecordingTransport(HttpResponse(
            200, {"content-type":"text/event-stream"}, b"",
            chunks=(b"event: token\ndata: one\n\n", b"event: done\ndata: ok\n\n"),
        ))
        streamed = PlanningReasoningAdapter(transport).invoke(adapter_request(
            "converseRequirement", payload={"message":"plan"}, response_mode="SSE",
        ))
        self.assertEqual(2, len(streamed.chunks))
        self.assertEqual(b"event: done\ndata: ok\n\n", streamed.chunks[1])

    def test_heterogeneous_adapter_changes_vendor_contract_without_changing_gateway_contract(self) -> None:
        transport = RecordingTransport(HttpResponse(200, {"content-type":"application/x-vendor+json"},
                                                   b'{"ok":"Y","output":{"brief":"HELLO"}}'))
        response = HeterogeneousFakeAdapter(transport).invoke(adapter_request(
            "summarize", payload={"text":"hello"}, upstream="http://127.0.0.1:19991",
        ))
        request, _ = transport.requests[0]
        vendor_body = json.loads(request.body)
        self.assertEqual(("POST", "http://127.0.0.1:19991/v7/execute"), (request.method, request.url))
        self.assertEqual("service-credential", request.headers["X-Vendor-Key"])
        self.assertNotIn("Authorization", request.headers)
        self.assertNotIn("X-GenB-Actor-Token", request.headers)
        self.assertEqual("MAKE_BRIEF", vendor_body["command"])
        self.assertTrue(vendor_body["subjectKey"].startswith("sha256:"))
        self.assertNotIn("user-a", json.dumps(vendor_body))
        self.assertEqual({"summary":"HELLO"}, json.loads(response.body))


if __name__ == "__main__": unittest.main()
