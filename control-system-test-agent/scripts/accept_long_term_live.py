"""Run the real GenB -> Control -> Runtime -> PostgreSQL Long-term Memory acceptance."""

import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx

from control_system_test_agent.clients import ControlSystemClient, GenBClient


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--genb-base-url", default="http://127.0.0.1:18581/api")
    parser.add_argument("--control-base-url", default="http://127.0.0.1:18701")
    parser.add_argument("--credentials", type=Path, required=True)
    args = parser.parse_args()
    credentials = json.loads(args.credentials.read_text(encoding="utf-8"))
    suffix = uuid4().hex[:12]
    async with httpx.AsyncClient(timeout=10) as http:
        login = await http.post(f"{args.genb_base_url}/v1/auth/login", json={
            "username": _required("GENB_TEST_USERNAME"), "password": _required("GENB_TEST_PASSWORD"),
        })
        user_token = login.json()["data"]["token"]
        genb = GenBClient(http, args.genb_base_url)
        control = ControlSystemClient(http, args.control_base_url)
        session_a = await genb.issue_component_session(
            user_token=user_token, service_credential=credentials["agentA"],
            agent_id="memory-test-a", session_id=f"lt-a-write-{suffix}",
            requested_components=("LONG_TERM_MEMORY",),
        )
        extraction_id = await control.request_long_term_extraction(
            service_credential=credentials["agentA"], actor_token=session_a.actor_token,
            turn_id=f"turn-{suffix}", user_message="用户长期偏好稳健产品，登录密码是 should-be-redacted",
            assistant_message="已记录长期偏好。", occurred_at="2026-07-24T01:00:00Z",
            request_id=f"req-{suffix}", idempotency_key=f"idem-{suffix}-long-term",
        )
        status = None
        for _ in range(50):
            status = await control.get_long_term_extraction(
                service_credential=credentials["agentA"], actor_token=session_a.actor_token,
                extraction_id=extraction_id, request_id=f"req-status-{suffix}",
            )
            if status.status in {"SUCCEEDED", "NO_WRITE", "FAILED", "DEAD"}:
                break
            await asyncio.sleep(0.2)
        assert status and status.status == "SUCCEEDED" and status.written_count == 1
        session_a2 = await genb.issue_component_session(
            user_token=user_token, service_credential=credentials["agentA"],
            agent_id="memory-test-a", session_id=f"lt-a-recall-{suffix}",
            requested_components=("LONG_TERM_MEMORY",),
        )
        own = await control.search_long_term_memory(
            service_credential=credentials["agentA"], actor_token=session_a2.actor_token,
            query="稳健", request_id=f"req-search-a-{suffix}",
        )
        session_b = await genb.issue_component_session(
            user_token=user_token, service_credential=credentials["agentB"],
            agent_id="memory-test-b", session_id=f"lt-b-recall-{suffix}",
            requested_components=("LONG_TERM_MEMORY",),
        )
        isolated = await control.search_long_term_memory(
            service_credential=credentials["agentB"], actor_token=session_b.actor_token,
            query="稳健", request_id=f"req-search-b-{suffix}",
        )
        assert len(own) >= 1 and isolated == ()
        assert all("should-be-redacted" not in item.content for item in own)
        deleted = await control.delete_long_term_memory(
            service_credential=credentials["agentA"], actor_token=session_a2.actor_token,
            memory_id=own[0].memory_id, reason="Iteration 13 acceptance soft delete",
            request_id=f"req-delete-{suffix}",
        )
        assert deleted
        after = await control.search_long_term_memory(
            service_credential=credentials["agentA"], actor_token=session_a2.actor_token,
            query="稳健", request_id=f"req-after-{suffix}",
        )
        assert after == ()
        denied = False
        try:
            await genb.issue_component_session(
                user_token=user_token, service_credential=credentials["unbound"],
                agent_id="memory-test-unbound", session_id=f"lt-unbound-{suffix}",
                requested_components=("LONG_TERM_MEMORY",),
            )
        except Exception:
            denied = True
        assert denied
    print("status=SUCCEEDED cross_session_hits>=1 isolated_hits=0 sensitive_echo=0 soft_delete=true unbound_denied=true")


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


if __name__ == "__main__":
    asyncio.run(main())
