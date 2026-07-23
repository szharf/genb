import json
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class SummaryMessage:
    turn_id: str
    role: str
    content: str


@dataclass(frozen=True)
class SummaryGenerationRequest:
    messages: tuple[SummaryMessage, ...]
    previous_summary: str | None
    model_alias: str
    request_id: str
    trace_parent: str | None = None
    capability: str = "SESSION_SUMMARY"


@dataclass(frozen=True)
class SummaryGenerationResult:
    summary: str
    model: str


class SummaryGenerator(Protocol):
    async def generate(
        self, request: SummaryGenerationRequest
    ) -> SummaryGenerationResult: ...


class UnavailableSummaryGenerator:
    async def health(self) -> bool:
        return False

    async def generate(self, request: SummaryGenerationRequest) -> SummaryGenerationResult:
        del request
        raise RuntimeError("Runtime Inference summary adapter is not configured")


class RuntimeInferenceSummaryGenerator:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        service_token: str,
        inference_url: str = "/api/v1/runtime-system/inference",
    ) -> None:
        if len(service_token) < 16:
            raise ValueError("Runtime Inference service token must contain at least 16 characters")
        self._client = client
        self._service_token = service_token
        self._inference_url = inference_url

    async def health(self) -> bool:
        try:
            response = await self._client.get("/health/ready")
            return response.status_code == 200 and len(response.content) <= 16_384
        except httpx.HTTPError:
            return False

    async def generate(
        self, request: SummaryGenerationRequest
    ) -> SummaryGenerationResult:
        payload = {
            "capability": request.capability,
            "modelAlias": request.model_alias,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Summarize only the visible conversation facts and final answers. "
                        "Do not include passwords, tokens, hidden reasoning, or unsupported facts."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "previousSummary": request.previous_summary,
                            "messages": [
                                {
                                    "turnId": message.turn_id,
                                    "role": message.role,
                                    "content": message.content,
                                }
                                for message in request.messages
                            ],
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._service_token}",
            "X-Request-Id": request.request_id,
        }
        if request.trace_parent:
            headers["traceparent"] = request.trace_parent
        response = await self._client.post(
            self._inference_url,
            headers=headers,
            json=payload,
        )
        if response.status_code != 200 or len(response.content) > 65_536:
            raise RuntimeError("Runtime Inference summary request failed")
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        summary = data.get("content") if isinstance(data, dict) else None
        model = data.get("model") if isinstance(data, dict) else None
        if not (
            isinstance(summary, str)
            and summary.strip()
            and isinstance(model, str)
            and model
        ):
            raise RuntimeError("Runtime Inference summary response is invalid")
        return SummaryGenerationResult(summary=summary.strip(), model=model)
