from fastapi.testclient import TestClient

from long_term_memory.acceptance_runtime import app


def test_acceptance_runtime_extracts_the_current_user_message() -> None:
    response = TestClient(app).post(
        "/api/v1/runtime-system/inference",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "USER_MESSAGE:\n我长期偏好审慎、低波动的对公授信方案\n\n"
                        "ASSISTANT_FINAL:\n好的"
                    ),
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["structured"] == {
        "memories": [
            {
                "type": "USER_PREFERENCE",
                "content": "我长期偏好审慎、低波动的对公授信方案",
                "confidence": 0.96,
                "action": "UPSERT",
            }
        ]
    }
