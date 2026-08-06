import asyncio
import json
import os
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import redis

from control_system_test_agent.clients import ControlSystemClient, GenBClient
from long_term_memory.extraction import _extraction_schema


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def require_local(url: str) -> str:
    if urlparse(url).hostname not in LOCAL_HOSTS:
        raise RuntimeError("formal acceptance only accepts local URLs")
    return url.rstrip("/")


def candidate_session_grants() -> list[str]:
    client = redis.Redis(
        host="127.0.0.1",
        port=6379,
        password=required("LOCAL_REDIS_PASSWORD"),
        decode_responses=True,
        socket_timeout=3,
    )
    try:
        grants: list[str] = []
        for key in client.scan_iter("agent:core-component-demo-agent:session:*"):
            value = client.get(key)
            if not value:
                continue
            payload = json.loads(value)
            grant = payload.get("session_grant")
            if isinstance(grant, str) and grant:
                grants.append(grant)
        return grants
    finally:
        client.close()


async def main() -> None:
    genb_url = require_local(
        os.getenv("GENB_BASE_URL", "http://127.0.0.1:8581/api")
    )
    memory_url = require_local(
        os.getenv("LONG_TERM_MEMORY_BASE_URL", "http://127.0.0.1:18702")
    )
    credential = required("LOCAL_AGENT_CREDENTIAL")
    if os.getenv("LTM_PROBE_RUNTIME", "").lower() == "true":
        async with httpx.AsyncClient(timeout=15) as http:
            response = await http.post(
                "http://127.0.0.1:18704/api/v1/runtime-system/inference",
                headers={
                    "Authorization": f"Bearer {credential}",
                    "X-Request-Id": f"req_ltm_probe_{uuid4().hex}",
                },
                json={
                    "capability": "MEMORY_EXTRACTION",
                    "modelAlias": "memory-extraction-default",
                    "messages": [
                        {"role": "system", "content": "Return only the requested JSON schema."},
                        {"role": "user", "content": "用户长期偏好稳健低波动产品。"},
                    ],
                    "responseFormat": {
                        "type": "JSON_SCHEMA",
                        "schemaName": "long_term_memory_extraction_v1",
                        "jsonSchema": _extraction_schema(),
                    },
                },
            )
        payload = response.json() if response.content else {}
        print(
            f"runtime_status={response.status_code} "
            f"runtime_code={payload.get('code', 'OK' if response.status_code == 200 else 'UNKNOWN')}"
        )
        return
    grants = candidate_session_grants()
    if not grants:
        raise RuntimeError("no 18714 customer session was found")
    suffix = uuid4().hex[:12]
    agent_id = "core-component-demo-agent"

    async with httpx.AsyncClient(timeout=15) as http:
        client = ControlSystemClient(http, "http://127.0.0.1:18701")
        genb = GenBClient(http, genb_url)
        write_session = None
        grant = None
        for candidate in grants:
            try:
                write_session = await genb.issue_component_session(
                    session_grant=candidate,
                    service_credential=credential,
                    agent_id=agent_id,
                    session_id=f"ltm-write-{suffix}",
                    requested_components=("LONG_TERM_MEMORY",),
                )
                grant = candidate
                break
            except Exception:
                continue
        if write_session is None or grant is None:
            raise RuntimeError("all local 18714 session grants were rejected by GenB")
        endpoint = next(
            (
                item
                for item in write_session.components
                if item.component_code == "LONG_TERM_MEMORY"
            ),
            None,
        )
        if (
            endpoint is None
            or endpoint.base_url.rstrip("/") != memory_url
            or endpoint.implementation_code != "long-term-memory-service-v1"
        ):
            raise RuntimeError("GenB LONG_TERM_MEMORY binding does not point to 18702")
        extraction_id = await client.request_long_term_extraction(
            base_url=memory_url,
            conversation_id=f"conversation-write-{suffix}",
            service_credential=credential,
            actor_token=write_session.actor_token,
            turn_id=f"turn-{suffix}",
            user_message="用户长期偏好稳健低波动产品。",
            assistant_message="已记录长期偏好。",
            occurred_at=datetime.now(UTC).isoformat(),
            request_id=f"req-write-{suffix}",
            idempotency_key=f"idem-formal-{suffix}",
        )
        status = None
        for _ in range(60):
            status = await client.get_long_term_extraction(
                base_url=memory_url,
                service_credential=credential,
                actor_token=write_session.actor_token,
                extraction_id=extraction_id,
                request_id=f"req-status-{suffix}",
            )
            if status.status in {"SUCCEEDED", "NO_WRITE", "FAILED", "DEAD"}:
                break
            await asyncio.sleep(0.25)
        if status is None or status.status != "SUCCEEDED":
            raise RuntimeError(f"extraction did not succeed: {status}")

        recall_session = await genb.issue_component_session(
            session_grant=grant,
            service_credential=credential,
            agent_id=agent_id,
            session_id=f"ltm-recall-{suffix}",
            requested_components=("LONG_TERM_MEMORY",),
        )
        recalled = await client.search_long_term_memory(
            base_url=memory_url,
            service_credential=credential,
            actor_token=recall_session.actor_token,
            query="稳健",
            source_types=("CONVERSATION",),
            request_id=f"req-search-{suffix}",
        )
        if not recalled:
            raise RuntimeError("cross-session recall returned no conversation memory")
        deleted = await client.delete_long_term_memory(
            base_url=memory_url,
            service_credential=credential,
            actor_token=recall_session.actor_token,
            memory_id=recalled[0].memory_id,
            reason="M3 formal local acceptance cleanup",
            request_id=f"req-delete-{suffix}",
        )
        after_delete = await client.search_long_term_memory(
            base_url=memory_url,
            service_credential=credential,
            actor_token=recall_session.actor_token,
            query="稳健",
            source_types=("CONVERSATION",),
            request_id=f"req-after-{suffix}",
        )
        if not deleted or after_delete:
            raise RuntimeError("soft-delete acceptance failed")

    print(
        "status=SUCCEEDED cross_session=true source=CONVERSATION "
        "soft_delete=true actor_token=true"
    )


if __name__ == "__main__":
    asyncio.run(main())
