import httpx

from long_term_memory.extraction import RuntimeInferenceExtractionModel


def test_runtime_inference_adapter_accepts_only_structured_memory_candidates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer runtime-token-123456"
        assert request.headers["x-request-id"].startswith("req_ltm_")
        payload = __import__("json").loads(request.content)
        assert payload["capability"] == "MEMORY_EXTRACTION"
        assert payload["responseFormat"]["type"] == "JSON_SCHEMA"
        confidence_schema = payload["responseFormat"]["jsonSchema"]["properties"][
            "memories"
        ]["items"]["properties"]["confidence"]
        assert confidence_schema == {"type": "number"}
        return httpx.Response(
            200,
            json={
                "data": {
                    "model": "memory-model-local",
                    "structured": {
                        "memories": [
                            {
                                "type": "USER_PREFERENCE",
                                "content": "用户偏好中文回答。",
                                "confidence": 0.96,
                                "action": "UPSERT",
                            }
                        ]
                    },
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = RuntimeInferenceExtractionModel(
        client=client,
        service_token="runtime-token-123456",
        inference_url="http://runtime.local/api/v1/runtime-system/inference",
        model_alias="memory-extraction-default",
    )

    result = adapter.extract(
        user_message="我偏好中文回答。",
        assistant_message="已了解。",
    )

    client.close()
    assert result.model == "memory-model-local"
    assert len(result.candidates) == 1
    assert result.candidates[0].memory_type == "USER_PREFERENCE"
