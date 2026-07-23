import math

from fastapi.testclient import TestClient

from runtime_system.app import create_app
from runtime_system.identity import StaticTokenIdentityVerifier
from runtime_system.provider import FakeModelProvider


def test_authorized_caller_can_embed_multiple_inputs_in_order() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"embed-token": {"component:inference-engine:embed"}}
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runtime-system/embeddings",
            headers={
                "Authorization": "Bearer embed-token",
                "X-Request-Id": "req-embed-001",
            },
            json={
                "modelAlias": "embedding-default",
                "inputs": ["第一段", "第二段"],
                "dimensions": 4,
                "purpose": "KNOWLEDGE_INDEXING",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["dimensions"] == 4
    assert [item["index"] for item in body["data"]["vectors"]] == [0, 1]
    assert all(len(item["embedding"]) == 4 for item in body["data"]["vectors"])
    assert all(
        math.isfinite(value)
        for item in body["data"]["vectors"]
        for value in item["embedding"]
    )
    assert body["meta"]["componentCode"] == "INFERENCE_ENGINE"


def test_embedding_rejects_provider_dimension_mismatch() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"embed-token": {"component:inference-engine:embed"}}
        ),
        provider=FakeModelProvider(embedding_vectors=[[0.1, 0.2]]),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/runtime-system/embeddings",
            headers={
                "Authorization": "Bearer embed-token",
                "X-Request-Id": "req-bad-dimensions",
            },
            json={
                "modelAlias": "embedding-default",
                "inputs": ["文本"],
                "dimensions": 4,
                "purpose": "KNOWLEDGE_INDEXING",
            },
        )

    assert response.status_code == 502
    assert response.json()["code"] == "MODEL_PROVIDER_BAD_RESPONSE"
