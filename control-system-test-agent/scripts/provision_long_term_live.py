"""Append an isolated Long-term Memory acceptance fixture to development GenB."""

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx

COMPONENT = "LONG_TERM_MEMORY"
IMPLEMENTATION = "control-long-term-memory-iteration13"
PROFILE = "iteration13-default"
AGENTS = ("memory-test-a", "memory-test-b", "memory-test-unbound")
SCOPES = (
    "component:long-term-memory:read",
    "component:long-term-memory:write",
    "component:long-term-memory:delete",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--genb-base-url", default="http://127.0.0.1:18581/api")
    parser.add_argument("--control-base-url", default="http://127.0.0.1:18701")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to rotate credentials: output already exists")
    with httpx.Client(timeout=10) as client:
        token = _data(client.post(
            f"{args.genb_base_url}/v1/auth/login",
            json={"username": _required("GENB_TEST_USERNAME"), "password": _required("GENB_TEST_PASSWORD")},
        ), "login")["token"]
        headers = {"Authorization": f"Bearer {token}"}
        for agent_id in AGENTS:
            _ensure_agent(client, args.genb_base_url, headers, agent_id)
        implementation = _ensure_implementation(
            client, args.genb_base_url, args.control_base_url, headers
        )
        config = _ensure_config(client, args.genb_base_url, headers)
        bindings = {
            agent_id: _ensure_binding(
                client, args.genb_base_url, headers, agent_id,
                implementation["implementationCode"], config["id"],
            )
            for agent_id in AGENTS[:2]
        }
        credentials = {
            "agentA": _credential(client, args.genb_base_url, headers, AGENTS[0]),
            "agentB": _credential(client, args.genb_base_url, headers, AGENTS[1]),
            "unbound": _credential(client, args.genb_base_url, headers, AGENTS[2]),
            "bindingIds": {key: value["id"] for key, value in bindings.items()},
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(credentials), encoding="utf-8")
    print("Long-term acceptance fixture provisioned; secrets were written only to the ignored output file.")


def _ensure_agent(client, base, headers, agent_id):
    if _optional_data(client.get(f"{base}/v1/agents/{agent_id}", headers=headers)) is not None:
        return
    _data(client.post(f"{base}/v1/agents", headers=headers, json={
        "agentId": agent_id, "name": f"核心组件验收智能体 {agent_id[-1].upper()}",
        "description": "Long-term Memory A/B隔离验收专用逻辑智能体",
        "category": "核心组件测试", "owner": "GenB Core Component Team",
        "tags": "memory-test,iteration13",
    }), f"create {agent_id}")


def _ensure_implementation(client, base, control_base, headers):
    detail = _data(client.get(f"{base}/v1/core-components/{COMPONENT}", headers=headers), "detail")
    existing = next((x for x in detail["implementations"] if x["implementationCode"] == IMPLEMENTATION), None)
    if existing is None:
        return _data(client.post(f"{base}/v1/core-components/{COMPONENT}/implementations", headers=headers, json={
            "implementationCode": IMPLEMENTATION, "owner": "control-system-team",
            "runtimeType": "HTTP", "interfaceVersion": "1.0.0",
            "baseUrl": control_base, "healthUrl": f"{control_base}/health/ready",
        }), "register implementation")
    if existing["status"] != "REGISTERED":
        return _data(client.post(f"{base}/v1/core-components/{COMPONENT}/implementations/{existing['id']}:enable", headers=headers), "enable implementation")
    return existing


def _ensure_config(client, base, headers):
    configs = _data(client.get(f"{base}/v1/core-components/{COMPONENT}/configs", headers=headers,
        params={"implementationCode": IMPLEMENTATION, "profileCode": PROFILE}), "configs")
    published = next((x for x in configs if x["status"] == "PUBLISHED"), None)
    if published:
        return published
    draft = _data(client.post(f"{base}/v1/core-components/{COMPONENT}/configs", headers=headers, json={
        "implementationCode": IMPLEMENTATION, "profileCode": PROFILE,
        "config": {
            "enabledTypes": ["USER_PREFERENCE", "STABLE_FACT", "USER_CONSTRAINT"],
            "autoExtractionEnabled": True, "confidenceThreshold": 0.8,
            "retentionDays": 30, "topK": 5, "maxTopK": 20,
            "modelAlias": "memory-acceptance", "maxAttempts": 3,
        },
        "secretRefs": [], "changeSummary": "Iteration 13 Long-term Memory acceptance baseline",
    }), "create config")
    return _data(client.post(f"{base}/v1/core-components/{COMPONENT}/configs/{draft['id']}:publish", headers=headers), "publish config")


def _ensure_binding(client, base, headers, agent_id, implementation_code, config_id):
    detail = _data(client.get(f"{base}/v1/core-components/{COMPONENT}", headers=headers), "bindings")
    existing = next((x for x in detail["bindings"] if x["agentId"] == agent_id), None)
    if existing and existing["status"] == "ENABLED" and existing["implementationCode"] == implementation_code and existing["configVersionId"] == config_id:
        return existing
    return _data(client.post(f"{base}/v1/core-components/{COMPONENT}/bindings", headers=headers, json={
        "agentId": agent_id, "implementationCode": implementation_code,
        "configVersionId": config_id,
    }), f"bind {agent_id}")


def _credential(client, base, headers, agent_id):
    return _data(client.post(f"{base}/v1/service-credentials", headers=headers, json={
        "agentId": agent_id, "name": f"Iteration 13 {agent_id} acceptance",
        "scopes": list(SCOPES),
    }), f"credential {agent_id}")["credentialSecret"]


def _data(response: httpx.Response, operation: str) -> Any:
    if not response.is_success:
        raise RuntimeError(f"{operation} failed with HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("code") != 200 or "data" not in payload:
        raise RuntimeError(f"{operation} returned an invalid response")
    return payload["data"]


def _optional_data(response: httpx.Response):
    if response.status_code == 404:
        return None
    try:
        return _data(response, "optional lookup")
    except RuntimeError:
        return None


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


if __name__ == "__main__":
    main()
