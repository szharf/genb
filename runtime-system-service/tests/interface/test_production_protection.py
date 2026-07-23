import asyncio

import httpx
from fastapi.testclient import TestClient

from runtime_system.app import create_app
from runtime_system.identity import StaticTokenIdentityVerifier
from runtime_system.models import InferenceRequest
from runtime_system.provider import FakeModelProvider, ProviderInferenceResult
from runtime_system.protection import RuntimeProtectionSettings


TOKEN = "runtime-secret-that-must-never-leak"
SCOPES = {
    "component:inference-engine:infer",
    "component:inference-engine:health:read",
}


def _client(settings: RuntimeProtectionSettings) -> TestClient:
    return TestClient(
        create_app(
            identity_verifier=StaticTokenIdentityVerifier(tokens={TOKEN: SCOPES}),
            protection_settings=settings,
        )
    )


def _request(content: str = "hello") -> dict[str, object]:
    return {
        "capability": "CHAT",
        "modelAlias": "chat-default",
        "messages": [{"role": "user", "content": content}],
    }


def test_oversized_model_input_is_rejected_before_provider_call() -> None:
    with _client(
        RuntimeProtectionSettings(
            max_input_characters=8,
            requests_per_window=10,
            window_seconds=60,
            max_concurrent_requests=2,
            acquire_timeout_seconds=0.05,
        )
    ) as client:
        response = client.post(
            "/api/v1/runtime-system/inference",
            headers={"Authorization": f"Bearer {TOKEN}", "X-Request-Id": "req-large"},
            json=_request("0123456789"),
        )

    assert response.status_code == 413
    assert response.json()["code"] == "MODEL_INPUT_LIMIT_EXCEEDED"
    assert response.json()["retryable"] is False
    assert "0123456789" not in response.text
    assert TOKEN not in response.text


def test_per_caller_rate_limit_is_bounded_and_observable_without_token_label() -> None:
    with _client(
        RuntimeProtectionSettings(
            max_input_characters=100,
            requests_per_window=1,
            window_seconds=60,
            max_concurrent_requests=2,
            acquire_timeout_seconds=0.05,
        )
    ) as client:
        first = client.post(
            "/api/v1/runtime-system/inference",
            headers={"Authorization": f"Bearer {TOKEN}", "X-Request-Id": "req-first"},
            json=_request(),
        )
        limited = client.post(
            "/api/v1/runtime-system/inference",
            headers={"Authorization": f"Bearer {TOKEN}", "X-Request-Id": "req-limited"},
            json=_request(),
        )
        metrics = client.get(
            "/internal/metrics",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert first.status_code == 200
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "60"
    assert limited.json()["code"] == "MODEL_RATE_LIMITED"
    assert metrics.status_code == 200
    assert 'runtime_protection_rejections_total{reason="rate_limit"} 1' in metrics.text
    assert TOKEN not in metrics.text


def test_metrics_require_health_scope() -> None:
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(
            tokens={"infer-only": {"component:inference-engine:infer"}}
        )
    )
    with TestClient(app) as client:
        missing = client.get("/internal/metrics")
        denied = client.get(
            "/internal/metrics", headers={"Authorization": "Bearer infer-only"}
        )

    assert missing.status_code == 401
    assert denied.status_code == 403


class BlockingProvider(FakeModelProvider):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def infer(self, request: InferenceRequest) -> ProviderInferenceResult:
        self.started.set()
        await self.release.wait()
        return await super().infer(request)


def test_concurrency_limit_rejects_quickly_and_recovers_after_release() -> None:
    asyncio.run(_exercise_concurrency_limit())


async def _exercise_concurrency_limit() -> None:
    provider = BlockingProvider()
    app = create_app(
        identity_verifier=StaticTokenIdentityVerifier(tokens={TOKEN: SCOPES}),
        provider=provider,
        protection_settings=RuntimeProtectionSettings(
            max_input_characters=100,
            requests_per_window=10,
            window_seconds=60,
            max_concurrent_requests=1,
            acquire_timeout_seconds=0.01,
        ),
    )
    headers = {"Authorization": f"Bearer {TOKEN}", "X-Request-Id": "req-one"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first_task = asyncio.create_task(
            client.post("/api/v1/runtime-system/inference", headers=headers, json=_request())
        )
        await provider.started.wait()
        rejected = await client.post(
            "/api/v1/runtime-system/inference",
            headers={**headers, "X-Request-Id": "req-two"},
            json=_request(),
        )
        provider.release.set()
        first = await first_task
        recovered = await client.post(
            "/api/v1/runtime-system/inference",
            headers={**headers, "X-Request-Id": "req-three"},
            json=_request(),
        )

    assert rejected.status_code == 503
    assert rejected.json()["code"] == "MODEL_CAPACITY_EXHAUSTED"
    assert first.status_code == 200
    assert recovered.status_code == 200
