"""Run the real GenB -> Test Agent -> Control System -> Redis acceptance matrix."""

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx
from redis import Redis

from control_system_test_agent.clients import ControlSystemClient, GenBClient
from control_system_test_agent.errors import RemoteCallError
from control_system_test_agent.orchestrator import DeterministicAnswerer, TestAgent


async def main_async() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--genb-base-url", default="http://127.0.0.1:18581/api")
    parser.add_argument("--control-base-url", default="http://127.0.0.1:18701")
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    credentials = json.loads(args.credentials.read_text(encoding="utf-8"))
    _require_distinct(credentials)
    redis = Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=_required_env("REDIS_PASSWORD"),
        db=int(os.getenv("REDIS_DB", "14")),
        decode_responses=True,
    )
    before = set(redis.scan_iter(match="genb:cs:v1:*"))
    evidence: dict[str, Any] = {"checks": {}}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8)) as http:
            user_token = await _login(http, args.genb_base_url)
            genb = GenBClient(http, args.genb_base_url)
            control = ControlSystemClient(http, args.control_base_url)
            agent_a = TestAgent(
                agent_id="memory-test-a",
                service_credential=credentials["agentA"],
                genb=genb,
                control=control,
                answerer=DeterministicAnswerer(),
            )
            agent_b = TestAgent(
                agent_id="memory-test-b",
                service_credential=credentials["agentB"],
                genb=genb,
                control=control,
                answerer=DeterministicAnswerer(),
            )

            first_a = await agent_a.chat(
                user_token=user_token,
                session_id="iteration11-a-shared",
                message="我偏好低风险产品",
            )
            second_a = await agent_a.chat(
                user_token=user_token,
                session_id="iteration11-a-shared",
                message="我的偏好是什么？",
            )
            other_session_a = await agent_a.chat(
                user_token=user_token,
                session_id="iteration11-a-other",
                message="这里能看到旧会话吗？",
            )
            first_b = await agent_b.chat(
                user_token=user_token,
                session_id="iteration11-a-shared",
                message="A的偏好是什么？",
            )
            assert first_a.context_message_count == 0 and first_a.committed
            assert second_a.context_message_count == 2 and second_a.committed
            assert other_session_a.context_message_count == 0 and other_session_a.committed
            assert first_b.context_message_count == 0 and first_b.committed
            evidence["checks"]["agentAContinuousRecall"] = "PASS"
            evidence["checks"]["sessionIsolation"] = "PASS"
            evidence["checks"]["agentIsolation"] = "PASS"

            await _expect_session_denied(
                genb,
                user_token=user_token,
                agent_id="memory-test-a",
                credential=credentials["agentB"],
                session_id="iteration11-wrong-credential",
            )
            evidence["checks"]["wrongCredentialDenied"] = "PASS"
            await _expect_session_denied(
                genb,
                user_token=user_token,
                agent_id="memory-test-unbound",
                credential=credentials["unbound"],
                session_id="iteration11-unbound",
            )
            evidence["checks"]["unboundAgentDenied"] = "PASS"

            read_only_agent = TestAgent(
                agent_id="memory-test-a",
                service_credential=credentials["agentAReadOnly"],
                genb=genb,
                control=control,
                answerer=DeterministicAnswerer(),
            )
            read_only_result = await read_only_agent.chat(
                user_token=user_token,
                session_id="iteration11-read-only",
                message="只读调用不能提交",
            )
            assert not read_only_result.committed
            assert read_only_result.warnings == ("SHORT_TERM_COMMIT_UNAVAILABLE",)
            evidence["checks"]["insufficientScopeDenied"] = "PASS"

            await _verify_disabled_binding_fails_closed(
                http=http,
                genb=genb,
                base_url=args.genb_base_url,
                user_token=user_token,
                credential=credentials["agentA"],
                binding_id=credentials["bindingIds"]["memory-test-a"],
            )
            evidence["checks"]["disabledBindingDeniedAndRestored"] = "PASS"

        after = set(redis.scan_iter(match="genb:cs:v1:*"))
        new_keys = after - before
        assert new_keys
        assert all(
            identity not in key
            for key in new_keys
            for identity in (
                "tenant-iteration11",
                "memory-test-a",
                "memory-test-b",
                "iteration11-a-shared",
            )
        )
        evidence["checks"]["redisKeysAreHashed"] = "PASS"
        evidence["redisNewKeyCountBeforeCleanup"] = len(new_keys)
    finally:
        current = set(redis.scan_iter(match="genb:cs:v1:*"))
        removable = current - before
        if removable:
            redis.delete(*removable)
        evidence["redisResidualNewKeyCount"] = len(
            set(redis.scan_iter(match="genb:cs:v1:*")) - before
        )
        redis.close()

    assert evidence["redisResidualNewKeyCount"] == 0
    evidence["checks"]["redisAcceptanceCleanup"] = "PASS"
    evidence["result"] = "PASS"
    evidence["topology"] = {
        "genb": args.genb_base_url,
        "controlSystem": args.control_base_url,
        "agents": ["memory-test-a", "memory-test-b"],
        "redisDb": int(os.getenv("REDIS_DB", "14")),
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False))


async def _login(client: httpx.AsyncClient, base_url: str) -> str:
    response = await client.post(
        f"{base_url.rstrip('/')}/v1/auth/login",
        json={
            "username": _required_env("GENB_TEST_USERNAME"),
            "password": _required_env("GENB_TEST_PASSWORD"),
        },
    )
    payload = response.json()
    if response.status_code != 200 or payload.get("code") != 200:
        raise RuntimeError(f"login failed (HTTP {response.status_code})")
    return payload["data"]["token"]


async def _expect_session_denied(
    genb: GenBClient,
    *,
    user_token: str,
    agent_id: str,
    credential: str,
    session_id: str,
) -> None:
    try:
        await genb.issue_component_session(
            user_token=user_token,
            service_credential=credential,
            agent_id=agent_id,
            session_id=session_id,
            requested_components=("SHORT_TERM_MEMORY",),
        )
    except RemoteCallError as error:
        assert error.status_code in {400, 403}
        return
    raise AssertionError("component session was unexpectedly issued")


async def _verify_disabled_binding_fails_closed(
    *,
    http: httpx.AsyncClient,
    genb: GenBClient,
    base_url: str,
    user_token: str,
    credential: str,
    binding_id: int,
) -> None:
    headers = {"Authorization": f"Bearer {user_token}"}
    disable_url = (
        f"{base_url.rstrip('/')}/v1/core-components/SHORT_TERM_MEMORY/bindings/"
        f"{binding_id}:disable"
    )
    enable_url = disable_url.removesuffix(":disable") + ":enable"
    response = await http.post(disable_url, headers=headers)
    assert response.status_code == 200 and response.json().get("code") == 200
    try:
        await _expect_session_denied(
            genb,
            user_token=user_token,
            agent_id="memory-test-a",
            credential=credential,
            session_id="iteration11-disabled-binding",
        )
    finally:
        response = await http.post(enable_url, headers=headers)
        assert response.status_code == 200 and response.json().get("code") == 200


def _require_distinct(credentials: dict[str, Any]) -> None:
    values = [
        credentials["agentA"],
        credentials["agentB"],
        credentials["unbound"],
        credentials["agentAReadOnly"],
    ]
    if len(set(values)) != len(values):
        raise RuntimeError("Each logical fixture must use a distinct service credential")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


if __name__ == "__main__":
    asyncio.run(main_async())
