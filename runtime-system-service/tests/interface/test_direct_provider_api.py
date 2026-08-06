import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from runtime_system.app import (
    EMBED_SCOPE,
    INFER_SCOPE,
    MODELS_READ_SCOPE,
    create_app,
)
from runtime_system.identity import StaticTokenIdentityVerifier
from runtime_system.routing import build_provider_from_document


def _chat_document() -> dict[str, object]:
    return {
        "schemaVersion": "1.0",
        "providers": [
            {
                "providerId": "direct-primary",
                "type": "OPENAI_COMPATIBLE",
                "baseUrl": "https://provider.example/v1",
                "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                "timeoutMs": 30000,
            }
        ],
        "routes": [
            {
                "routeId": "chat-primary",
                "modelAlias": "chat-default",
                "capabilities": ["CHAT"],
                "providerId": "direct-primary",
                "model": "direct-chat-model-v1",
            }
        ],
    }


def _build_chat_provider(
    transport: httpx.AsyncBaseTransport,
    *,
    capabilities: list[str] | None = None,
):
    document = _chat_document()
    document["routes"][0]["capabilities"] = capabilities or ["CHAT"]
    return build_provider_from_document(
        document,
        environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        transport=transport,
    )


def _inference_app(provider):
    return create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"caller-token": {INFER_SCOPE}}
        ),
        provider=provider,
    )


def test_configured_direct_provider_serves_inference_through_runtime_interface():
    upstream_requests: list[httpx.Request] = []

    def handle_upstream(request: httpx.Request) -> httpx.Response:
        upstream_requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "model": "direct-chat-model-v1",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "你好"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 2,
                    "total_tokens": 10,
                },
            },
        )

    provider = build_provider_from_document(
        {
            "schemaVersion": "1.0",
            "providers": [
                {
                    "providerId": "direct-primary",
                    "type": "OPENAI_COMPATIBLE",
                    "baseUrl": "https://provider.example/v1",
                    "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                    "timeoutMs": 30000,
                }
            ],
            "routes": [
                {
                    "routeId": "chat-primary",
                    "modelAlias": "chat-default",
                    "capabilities": ["CHAT", "STREAM"],
                    "providerId": "direct-primary",
                    "model": "direct-chat-model-v1",
                }
            ],
        },
        environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        transport=httpx.MockTransport(handle_upstream),
    )
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"caller-token": {INFER_SCOPE}}
        ),
        provider=provider,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-direct-1",
            },
            json={
                "capability": "CHAT",
                "modelAlias": "chat-default",
                "messages": [{"role": "user", "content": "你好"}],
            },
        )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "content": "你好",
        "structured": None,
        "modelAlias": "chat-default",
        "model": "direct-chat-model-v1",
        "provider": "direct-primary",
        "usage": {
            "inputTokens": 8,
            "outputTokens": 2,
            "totalTokens": 10,
            "estimated": False,
        },
        "finishReason": "STOP",
    }
    assert len(upstream_requests) == 1
    upstream = upstream_requests[0]
    assert upstream.url == "https://provider.example/v1/chat/completions"
    assert upstream.headers["authorization"] == "Bearer test-token"
    assert json.loads(upstream.content) == {
        "model": "direct-chat-model-v1",
        "messages": [{"role": "user", "content": "你好"}],
        "stream": False,
    }


def test_unknown_model_alias_returns_provider_unavailable_problem():
    provider = build_provider_from_document(
        {
            "schemaVersion": "1.0",
            "providers": [
                {
                    "providerId": "direct-primary",
                    "type": "OPENAI_COMPATIBLE",
                    "baseUrl": "https://provider.example/v1",
                    "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                    "timeoutMs": 30000,
                }
            ],
            "routes": [
                {
                    "routeId": "chat-primary",
                    "modelAlias": "chat-default",
                    "capabilities": ["CHAT"],
                    "providerId": "direct-primary",
                    "model": "direct-chat-model-v1",
                }
            ],
        },
        environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(500, json={})
        ),
    )
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"caller-token": {INFER_SCOPE}}
        ),
        provider=provider,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-direct-missing",
            },
            json={
                "capability": "CHAT",
                "modelAlias": "missing-alias",
                "messages": [{"role": "user", "content": "你好"}],
            },
        )

    assert response.status_code == 503
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert response.json() == {
        "type": "https://errors.genb.local/model-provider-unavailable",
        "title": "Model provider is unavailable",
        "status": 503,
        "detail": "No published route is available for the requested model alias and capability.",
        "code": "MODEL_PROVIDER_UNAVAILABLE",
        "requestId": "req-direct-missing",
        "retryable": True,
    }


def test_provider_rate_limit_is_normalized_without_leaking_upstream_body():
    provider = build_provider_from_document(
        {
            "schemaVersion": "1.0",
            "providers": [
                {
                    "providerId": "direct-primary",
                    "type": "OPENAI_COMPATIBLE",
                    "baseUrl": "https://provider.example/v1",
                    "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                    "timeoutMs": 30000,
                }
            ],
            "routes": [
                {
                    "routeId": "chat-primary",
                    "modelAlias": "chat-default",
                    "capabilities": ["CHAT"],
                    "providerId": "direct-primary",
                    "model": "direct-chat-model-v1",
                }
            ],
        },
        environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                429,
                headers={"Retry-After": "2"},
                json={"error": {"message": "sensitive upstream detail"}},
            )
        ),
    )
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"caller-token": {INFER_SCOPE}}
        ),
        provider=provider,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-direct-rate-limit",
            },
            json={
                "capability": "CHAT",
                "modelAlias": "chat-default",
                "messages": [{"role": "user", "content": "你好"}],
            },
        )

    assert response.status_code == 429
    assert response.json() == {
        "type": "https://errors.genb.local/model-rate-limited",
        "title": "Model provider rate limit was reached",
        "status": 429,
        "detail": "The selected model provider temporarily rejected the request due to rate limiting.",
        "code": "MODEL_RATE_LIMITED",
        "requestId": "req-direct-rate-limit",
        "retryable": True,
    }
    assert "sensitive upstream detail" not in response.text


def test_configured_direct_provider_serves_embeddings_in_input_order():
    upstream_requests: list[httpx.Request] = []

    def handle_upstream(request: httpx.Request) -> httpx.Response:
        upstream_requests.append(request)
        return httpx.Response(
            200,
            json={
                "model": "direct-embedding-v1",
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                    {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                ],
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            },
        )

    provider = build_provider_from_document(
        {
            "schemaVersion": "1.0",
            "providers": [
                {
                    "providerId": "direct-primary",
                    "type": "OPENAI_COMPATIBLE",
                    "baseUrl": "https://provider.example/v1",
                    "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                    "timeoutMs": 30000,
                }
            ],
            "routes": [
                {
                    "routeId": "embedding-primary",
                    "modelAlias": "embedding-default",
                    "capabilities": ["EMBEDDING"],
                    "providerId": "direct-primary",
                    "model": "direct-embedding-v1",
                    "dimensions": [3],
                }
            ],
        },
        environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        transport=httpx.MockTransport(handle_upstream),
    )
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"caller-token": {EMBED_SCOPE}}
        ),
        provider=provider,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/embeddings",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-direct-embedding",
            },
            json={
                "modelAlias": "embedding-default",
                "inputs": ["甲", "乙"],
                "dimensions": 3,
                "purpose": "LONG_TERM_MEMORY_RETRIEVAL",
            },
        )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "vectors": [
            {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            {"index": 1, "embedding": [0.4, 0.5, 0.6]},
        ],
        "modelAlias": "embedding-default",
        "model": "direct-embedding-v1",
        "provider": "direct-primary",
        "dimensions": 3,
        "usage": {"inputTokens": 5, "estimated": False},
    }
    assert json.loads(upstream_requests[0].content) == {
        "model": "direct-embedding-v1",
        "input": ["甲", "乙"],
        "dimensions": 3,
    }


def test_models_catalog_is_derived_from_published_routes():
    provider = build_provider_from_document(
        {
            "schemaVersion": "1.0",
            "providers": [
                {
                    "providerId": "direct-primary",
                    "type": "OPENAI_COMPATIBLE",
                    "baseUrl": "https://provider.example/v1",
                    "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                    "timeoutMs": 30000,
                }
            ],
            "routes": [
                {
                    "routeId": "memory-primary",
                    "modelAlias": "memory-extraction-default",
                    "capabilities": ["CHAT", "JSON_SCHEMA"],
                    "providerId": "direct-primary",
                    "model": "direct-chat-model-v1",
                },
                {
                    "routeId": "embedding-primary",
                    "modelAlias": "embedding-default-v1",
                    "capabilities": ["EMBEDDING"],
                    "providerId": "direct-primary",
                    "model": "direct-embedding-v1",
                    "dimensions": [768, 1024],
                },
            ],
        },
        environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(500, json={})
        ),
    )
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"caller-token": {MODELS_READ_SCOPE}}
        ),
        provider=provider,
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/runtime-system/models",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-direct-models",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "data": [
            {
                "modelAlias": "embedding-default-v1",
                "capabilities": ["EMBEDDING"],
                "dimensions": [768, 1024],
                "status": "AVAILABLE",
            },
            {
                "modelAlias": "memory-extraction-default",
                "capabilities": ["CHAT", "JSON_SCHEMA"],
                "status": "AVAILABLE",
            },
        ]
    }


def test_duplicate_model_alias_is_rejected_before_runtime_starts():
    document = {
        "schemaVersion": "1.0",
        "providers": [
            {
                "providerId": "direct-primary",
                "type": "OPENAI_COMPATIBLE",
                "baseUrl": "https://provider.example/v1",
                "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                "timeoutMs": 30000,
            }
        ],
        "routes": [
            {
                "routeId": "chat-primary",
                "modelAlias": "chat-default",
                "capabilities": ["CHAT"],
                "providerId": "direct-primary",
                "model": "direct-chat-model-v1",
            },
            {
                "routeId": "chat-shadow",
                "modelAlias": "chat-default",
                "capabilities": ["CHAT"],
                "providerId": "direct-primary",
                "model": "direct-chat-model-v2",
            },
        ],
    }

    with pytest.raises(ValueError, match="Duplicate modelAlias: chat-default"):
        build_provider_from_document(
            document,
            environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        )


def test_structured_output_schema_is_sent_to_direct_provider_and_revalidated():
    upstream_requests: list[httpx.Request] = []

    def handle_upstream(request: httpx.Request) -> httpx.Response:
        upstream_requests.append(request)
        return httpx.Response(
            200,
            json={
                "model": "direct-chat-model-v1",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"memories":[]}',
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 6, "completion_tokens": 4},
            },
        )

    provider = build_provider_from_document(
        {
            "schemaVersion": "1.0",
            "providers": [
                {
                    "providerId": "direct-primary",
                    "type": "OPENAI_COMPATIBLE",
                    "baseUrl": "https://provider.example/v1",
                    "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                    "timeoutMs": 30000,
                }
            ],
            "routes": [
                {
                    "routeId": "memory-primary",
                    "modelAlias": "memory-extraction-default",
                    "capabilities": ["CHAT", "JSON_SCHEMA"],
                    "providerId": "direct-primary",
                    "model": "direct-chat-model-v1",
                }
            ],
        },
        environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        transport=httpx.MockTransport(handle_upstream),
    )
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"caller-token": {INFER_SCOPE}}
        ),
        provider=provider,
    )
    memory_schema = {
        "type": "object",
        "required": ["memories"],
        "properties": {"memories": {"type": "array"}},
        "additionalProperties": False,
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-direct-structured",
            },
            json={
                "capability": "MEMORY_EXTRACTION",
                "modelAlias": "memory-extraction-default",
                "messages": [{"role": "user", "content": "记住我喜欢茶"}],
                "responseFormat": {
                    "type": "JSON_SCHEMA",
                    "schemaName": "memory_extraction_v1",
                    "jsonSchema": memory_schema,
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["structured"] == {"memories": []}
    upstream_payload = json.loads(upstream_requests[0].content)
    assert upstream_payload["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "memory_extraction_v1",
            "strict": True,
            "schema": memory_schema,
        },
    }


def test_json_object_provider_mode_keeps_runtime_schema_validation():
    upstream_requests: list[httpx.Request] = []

    def handle_upstream(request: httpx.Request) -> httpx.Response:
        upstream_requests.append(request)
        return httpx.Response(
            200,
            json={
                "model": "deepseek-chat",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"memories":[]}',
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 6, "completion_tokens": 4},
            },
        )

    provider = build_provider_from_document(
        {
            "schemaVersion": "1.0",
            "providers": [
                {
                    "providerId": "deepseek-direct",
                    "type": "OPENAI_COMPATIBLE",
                    "baseUrl": "https://api.deepseek.com/v1",
                    "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                    "timeoutMs": 30000,
                    "structuredOutputMode": "JSON_OBJECT",
                }
            ],
            "routes": [
                {
                    "routeId": "memory-primary",
                    "modelAlias": "memory-extraction-default",
                    "capabilities": ["CHAT", "JSON_SCHEMA"],
                    "providerId": "deepseek-direct",
                    "model": "deepseek-chat",
                }
            ],
        },
        environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        transport=httpx.MockTransport(handle_upstream),
    )
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"caller-token": {INFER_SCOPE}}
        ),
        provider=provider,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-json-object-structured",
            },
            json={
                "capability": "MEMORY_EXTRACTION",
                "modelAlias": "memory-extraction-default",
                "messages": [{"role": "user", "content": "记住我喜欢茶"}],
                "responseFormat": {
                    "type": "JSON_SCHEMA",
                    "schemaName": "memory_extraction_v1",
                    "jsonSchema": {
                        "type": "object",
                        "required": ["memories"],
                        "properties": {"memories": {"type": "array"}},
                        "additionalProperties": False,
                    },
                },
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["structured"] == {"memories": []}
    upstream_payload = json.loads(upstream_requests[0].content)
    assert upstream_payload["response_format"] == {"type": "json_object"}
    assert upstream_payload["messages"][0]["role"] == "system"
    assert "memory_extraction_v1" in upstream_payload["messages"][0]["content"]
    assert '"required":["memories"]' in upstream_payload["messages"][0]["content"]


def test_route_referencing_unknown_provider_is_rejected_before_startup():
    document = {
        "schemaVersion": "1.0",
        "providers": [
            {
                "providerId": "direct-primary",
                "type": "OPENAI_COMPATIBLE",
                "baseUrl": "https://provider.example/v1",
                "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                "timeoutMs": 30000,
            }
        ],
        "routes": [
            {
                "routeId": "chat-primary",
                "modelAlias": "chat-default",
                "capabilities": ["CHAT"],
                "providerId": "missing-provider",
                "model": "direct-chat-model-v1",
            }
        ],
    }

    with pytest.raises(
        ValueError,
        match="Route chat-primary references unknown providerId: missing-provider",
    ):
        build_provider_from_document(
            document,
            environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        )


def test_runtime_build_app_loads_published_routing_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_path = tmp_path / "model-routing.json"
    config_path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "providers": [
                    {
                        "providerId": "direct-primary",
                        "type": "OPENAI_COMPATIBLE",
                        "baseUrl": "https://provider.example/v1",
                        "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                        "timeoutMs": 30000,
                    }
                ],
                "routes": [
                    {
                        "routeId": "chat-primary",
                        "modelAlias": "chat-published",
                        "capabilities": ["CHAT"],
                        "providerId": "direct-primary",
                        "model": "direct-chat-model-v1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MODEL_ROUTING_CONFIG", str(config_path))
    monkeypatch.setenv("TEST_DIRECT_PROVIDER_TOKEN", "test-token")
    monkeypatch.setenv("RUNTIME_STATIC_TOKEN", "caller-token")
    monkeypatch.setenv("APP_ENV", "local")

    from runtime_system.main import build_app

    with TestClient(build_app()) as client:
        response = client.get(
            "/api/v1/runtime-system/models",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-published-models",
            },
        )

    assert response.status_code == 200
    assert response.json()["data"] == [
        {
            "modelAlias": "chat-published",
            "capabilities": ["CHAT"],
            "status": "AVAILABLE",
        }
    ]


def test_provider_server_failure_is_normalized_as_unavailable():
    provider = build_provider_from_document(
        {
            "schemaVersion": "1.0",
            "providers": [
                {
                    "providerId": "direct-primary",
                    "type": "OPENAI_COMPATIBLE",
                    "baseUrl": "https://provider.example/v1",
                    "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                    "timeoutMs": 30000,
                }
            ],
            "routes": [
                {
                    "routeId": "chat-primary",
                    "modelAlias": "chat-default",
                    "capabilities": ["CHAT"],
                    "providerId": "direct-primary",
                    "model": "direct-chat-model-v1",
                }
            ],
        },
        environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                503,
                json={"error": {"message": "internal provider topology"}},
            )
        ),
    )
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"caller-token": {INFER_SCOPE}}
        ),
        provider=provider,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-direct-unavailable",
            },
            json={
                "capability": "CHAT",
                "modelAlias": "chat-default",
                "messages": [{"role": "user", "content": "你好"}],
            },
        )

    assert response.status_code == 503
    assert response.json()["code"] == "MODEL_PROVIDER_UNAVAILABLE"
    assert response.json()["retryable"] is True
    assert "internal provider topology" not in response.text


def test_malformed_provider_response_is_normalized_as_bad_response():
    provider = build_provider_from_document(
        {
            "schemaVersion": "1.0",
            "providers": [
                {
                    "providerId": "direct-primary",
                    "type": "OPENAI_COMPATIBLE",
                    "baseUrl": "https://provider.example/v1",
                    "secretRef": "env://TEST_DIRECT_PROVIDER_TOKEN",
                    "timeoutMs": 30000,
                }
            ],
            "routes": [
                {
                    "routeId": "chat-primary",
                    "modelAlias": "chat-default",
                    "capabilities": ["CHAT"],
                    "providerId": "direct-primary",
                    "model": "direct-chat-model-v1",
                }
            ],
        },
        environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"choices": []})
        ),
    )
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"caller-token": {INFER_SCOPE}}
        ),
        provider=provider,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-direct-malformed",
            },
            json={
                "capability": "CHAT",
                "modelAlias": "chat-default",
                "messages": [{"role": "user", "content": "你好"}],
            },
        )

    assert response.status_code == 502
    assert response.json()["code"] == "MODEL_PROVIDER_BAD_RESPONSE"
    assert response.json()["retryable"] is True


def test_provider_timeout_is_normalized_as_retryable_timeout():
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timed out", request=request)

    app = _inference_app(
        _build_chat_provider(httpx.MockTransport(timeout))
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-direct-timeout",
            },
            json={
                "capability": "CHAT",
                "modelAlias": "chat-default",
                "messages": [{"role": "user", "content": "你好"}],
            },
        )

    assert response.status_code == 504
    assert response.json()["code"] == "MODEL_TIMEOUT"
    assert response.json()["retryable"] is True


def test_configured_direct_provider_streams_deltas_through_sse_interface():
    upstream_requests: list[httpx.Request] = []

    def stream_response(request: httpx.Request) -> httpx.Response:
        upstream_requests.append(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=(
                'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"好"}}]}\n\n'
                "data: [DONE]\n\n"
            ).encode(),
        )

    app = _inference_app(
        _build_chat_provider(
            httpx.MockTransport(stream_response),
            capabilities=["CHAT", "STREAM"],
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/inference:stream",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-direct-stream",
            },
            json={
                "capability": "CHAT",
                "modelAlias": "chat-default",
                "messages": [{"role": "user", "content": "问候"}],
            },
        )

    assert response.status_code == 200
    assert '"content":"你"' in response.text
    assert '"content":"好"' in response.text
    assert "event: response.completed" in response.text
    assert json.loads(upstream_requests[0].content)["stream"] is True


def test_duplicate_provider_id_is_rejected_before_runtime_starts():
    document = _chat_document()
    document["providers"].append(
        {
            "providerId": "direct-primary",
            "type": "OPENAI_COMPATIBLE",
            "baseUrl": "https://second.example/v1",
            "secretRef": "env://SECOND_DIRECT_PROVIDER_TOKEN",
            "timeoutMs": 30000,
        }
    )

    with pytest.raises(ValueError, match="Duplicate providerId: direct-primary"):
        build_provider_from_document(
            document,
            environment={
                "TEST_DIRECT_PROVIDER_TOKEN": "test-token",
                "SECOND_DIRECT_PROVIDER_TOKEN": "second-token",
            },
        )


def test_embedding_dimension_not_published_by_route_is_rejected():
    upstream_called = False

    def upstream(_request: httpx.Request) -> httpx.Response:
        nonlocal upstream_called
        upstream_called = True
        return httpx.Response(500)

    document = _chat_document()
    document["routes"] = [
        {
            "routeId": "embedding-primary",
            "modelAlias": "embedding-default-v1",
            "capabilities": ["EMBEDDING"],
            "providerId": "direct-primary",
            "model": "direct-embedding-v1",
            "dimensions": [3],
        }
    ]
    provider = build_provider_from_document(
        document,
        environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        transport=httpx.MockTransport(upstream),
    )
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"caller-token": {EMBED_SCOPE}}
        ),
        provider=provider,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/runtime-system/embeddings",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-dimension-denied",
            },
            json={
                "modelAlias": "embedding-default-v1",
                "inputs": ["甲"],
                "dimensions": 4,
                "purpose": "LONG_TERM_MEMORY_RETRIEVAL",
            },
        )

    assert response.status_code == 400
    assert response.json()["code"] == "MODEL_REQUEST_INVALID"
    assert upstream_called is False


def test_non_http_provider_base_url_is_rejected_before_runtime_starts():
    document = _chat_document()
    document["providers"][0]["baseUrl"] = "file:///etc/passwd"

    with pytest.raises(ValueError, match="baseUrl must use http or https"):
        build_provider_from_document(
            document,
            environment={"TEST_DIRECT_PROVIDER_TOKEN": "test-token"},
        )


def test_stream_provider_failure_is_returned_as_terminal_sse_error():
    app = _inference_app(
        _build_chat_provider(
            httpx.MockTransport(
                lambda _request: httpx.Response(503, json={})
            ),
            capabilities=["CHAT", "STREAM"],
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/inference:stream",
            headers={
                "Authorization": "Bearer caller-token",
                "X-Request-Id": "req-direct-stream-failure",
            },
            json={
                "capability": "CHAT",
                "modelAlias": "chat-default",
                "messages": [{"role": "user", "content": "问候"}],
            },
        )

    assert response.status_code == 200
    assert "event: response.error" in response.text
    assert '"code":"MODEL_PROVIDER_UNAVAILABLE"' in response.text
    assert "event: response.completed" not in response.text
