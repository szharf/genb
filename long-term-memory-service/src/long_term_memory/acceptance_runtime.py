"""Local deterministic Runtime stub used only by the M3 acceptance scripts."""

import json
from typing import Any

from fastapi import FastAPI, Request


app = FastAPI(title="Long-term memory local acceptance Runtime")


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "UP"}


@app.post("/api/v1/runtime/inference")
@app.post("/api/v1/runtime-system/inference")
async def infer(request: Request) -> dict[str, Any]:
    body = await request.json()
    prompt = _last_user_prompt(body)
    user_message = _user_message_from_extraction_prompt(prompt)
    memory_type = (
        "USER_PREFERENCE" if "偏好" in user_message else "STABLE_FACT"
    )
    structured = {
        "memories": [
            {
                "type": memory_type,
                "content": user_message,
                "confidence": 0.96,
                "action": "UPSERT",
            }
        ]
    }
    encoded = json.dumps(structured, ensure_ascii=False)
    return {
        "data": {
            "content": encoded,
            "structured": structured,
            "modelAlias": body.get("modelAlias", "memory-extraction-default"),
            "model": "memory-acceptance-deterministic-v1",
            "provider": "LOCAL_ACCEPTANCE",
            "usage": {
                "inputTokens": len(prompt),
                "outputTokens": len(encoded),
                "totalTokens": len(prompt) + len(encoded),
                "estimated": True,
            },
            "finishReason": "STOP",
        },
        "meta": {
            "requestId": request.headers.get("X-Request-Id", "local-acceptance"),
            "componentCode": "INFERENCE_ENGINE",
            "implementationCode": "memory-acceptance-runtime-local",
            "interfaceVersion": "v1",
            "degraded": False,
        },
    }


def _last_user_prompt(body: dict[str, Any]) -> str:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            content = message.get("content")
            return content if isinstance(content, str) else ""
    return ""


def _user_message_from_extraction_prompt(prompt: str) -> str:
    marker = "USER_MESSAGE:\n"
    end_marker = "\n\nASSISTANT_FINAL:"
    if marker not in prompt:
        return prompt.strip()
    value = prompt.split(marker, 1)[1]
    if end_marker in value:
        value = value.split(end_marker, 1)[0]
    return value.strip()
