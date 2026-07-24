"""Append an isolated A/B acceptance fixture to a development GenB instance."""

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx


COMPONENT = "SHORT_TERM_MEMORY"
IMPLEMENTATION = "control-short-term-memory-iteration11"
PROFILE = "iteration11-default"
AGENTS = ("memory-test-a", "memory-test-b", "memory-test-unbound")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--genb-base-url", default="http://127.0.0.1:18581/api")
    parser.add_argument("--control-base-url", default="http://127.0.0.1:18701")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to rotate credentials: output already exists")
    username = _required_env("GENB_TEST_USERNAME")
    password = _required_env("GENB_TEST_PASSWORD")
    with httpx.Client(timeout=10) as client:
        token = _data(
            client.post(
                f"{args.genb_base_url.rstrip('/')}/v1/auth/login",
                json={"username": username, "password": password},
            ),
            "login",
        )["token"]
        headers = {"Authorization": f"Bearer {token}"}
        for agent_id in AGENTS:
            _ensure_agent(client, args.genb_base_url, headers, agent_id)
        implementation = _ensure_implementation(
            client, args.genb_base_url, args.control_base_url, headers
        )
        config = _ensure_config(client, args.genb_base_url, headers)
        bindings = {
            agent_id: _ensure_binding(
                client,
                args.genb_base_url,
                headers,
                agent_id,
                implementation["implementationCode"],
                config["id"],
            )
            for agent_id in AGENTS[:2]
        }
        credentials = {
            "agentA": _issue_credential(client, args.genb_base_url, headers, AGENTS[0]),
            "agentB": _issue_credential(client, args.genb_base_url, headers, AGENTS[1]),
            "unbound": _issue_credential(client, args.genb_base_url, headers, AGENTS[2]),
            "bindingIds": {key: value["id"] for key, value in bindings.items()},
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(credentials), encoding="utf-8")
    print(
        "Provisioned memory-test-a, memory-test-b and an unbound negative fixture; "
        "credential values were written only to the ignored acceptance file."
    )


def _ensure_agent(
    client: httpx.Client, base: str, headers: dict[str, str], agent_id: str
) -> None:
    response = client.get(f"{base.rstrip('/')}/v1/agents/{agent_id}", headers=headers)
    if _optional_data(response) is not None:
        return
    _data(
        client.post(
            f"{base.rstrip('/')}/v1/agents",
            headers=headers,
            json={
                "agentId": agent_id,
                "name": f"核心组件验收智能体 {agent_id[-1].upper()}",
                "description": "Iteration 11 A/B隔离自动验收专用逻辑智能体",
                "category": "核心组件测试",
                "owner": "GenB Core Component Team",
                "tags": "memory-test,iteration11",
            },
        ),
        f"create agent {agent_id}",
    )


def _ensure_implementation(
    client: httpx.Client,
    base: str,
    control_base: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    detail = _data(
        client.get(f"{base.rstrip('/')}/v1/core-components/{COMPONENT}", headers=headers),
        "read component detail",
    )
    existing = next(
        (item for item in detail["implementations"] if item["implementationCode"] == IMPLEMENTATION),
        None,
    )
    if existing is None:
        return _data(
            client.post(
                f"{base.rstrip('/')}/v1/core-components/{COMPONENT}/implementations",
                headers=headers,
                json={
                    "implementationCode": IMPLEMENTATION,
                    "owner": "control-system-team",
                    "runtimeType": "HTTP",
                    "interfaceVersion": "1.0.0",
                    "baseUrl": control_base.rstrip("/"),
                    "healthUrl": f"{control_base.rstrip('/')}/health/ready",
                },
            ),
            "register implementation",
        )
    if existing["status"] != "REGISTERED":
        return _data(
            client.post(
                f"{base.rstrip('/')}/v1/core-components/{COMPONENT}/implementations/"
                f"{existing['id']}:enable",
                headers=headers,
            ),
            "enable implementation",
        )
    return existing


def _ensure_config(
    client: httpx.Client, base: str, headers: dict[str, str]
) -> dict[str, Any]:
    configs = _data(
        client.get(
            f"{base.rstrip('/')}/v1/core-components/{COMPONENT}/configs",
            headers=headers,
            params={"implementationCode": IMPLEMENTATION, "profileCode": PROFILE},
        ),
        "list configs",
    )
    published = next((item for item in configs if item["status"] == "PUBLISHED"), None)
    if published is not None:
        return published
    draft = _data(
        client.post(
            f"{base.rstrip('/')}/v1/core-components/{COMPONENT}/configs",
            headers=headers,
            json={
                "implementationCode": IMPLEMENTATION,
                "profileCode": PROFILE,
                "config": {"ttlSeconds": 86400, "maxTurns": 50, "maxContextTokens": 2000},
                "secretRefs": [],
                "changeSummary": "Iteration 11 A/B acceptance baseline",
            },
        ),
        "create config",
    )
    return _data(
        client.post(
            f"{base.rstrip('/')}/v1/core-components/{COMPONENT}/configs/{draft['id']}:publish",
            headers=headers,
        ),
        "publish config",
    )


def _ensure_binding(
    client: httpx.Client,
    base: str,
    headers: dict[str, str],
    agent_id: str,
    implementation_code: str,
    config_id: int,
) -> dict[str, Any]:
    detail = _data(
        client.get(f"{base.rstrip('/')}/v1/core-components/{COMPONENT}", headers=headers),
        "read component bindings",
    )
    existing = next((item for item in detail["bindings"] if item["agentId"] == agent_id), None)
    if existing is not None:
        if existing["implementationCode"] != implementation_code:
            raise RuntimeError(f"{agent_id} already has an incompatible binding")
        if existing["status"] != "ENABLED":
            return _data(
                client.post(
                    f"{base.rstrip('/')}/v1/core-components/{COMPONENT}/bindings/"
                    f"{existing['id']}:enable",
                    headers=headers,
                ),
                f"enable binding {agent_id}",
            )
        return existing
    return _data(
        client.post(
            f"{base.rstrip('/')}/v1/core-components/{COMPONENT}/bindings",
            headers=headers,
            json={
                "agentId": agent_id,
                "implementationCode": implementation_code,
                "configVersionId": config_id,
            },
        ),
        f"bind {agent_id}",
    )


def _issue_credential(
    client: httpx.Client,
    base: str,
    headers: dict[str, str],
    agent_id: str,
) -> str:
    data = _data(
        client.post(
            f"{base.rstrip('/')}/v1/service-credentials",
            headers=headers,
            json={
                "agentId": agent_id,
                "name": f"Iteration 11 {agent_id} acceptance",
            },
        ),
        f"issue credential {agent_id}",
    )
    return data["credentialSecret"]


def _data(response: httpx.Response, operation: str) -> Any:
    payload = _payload(response, operation)
    if payload.get("code") != 200 or payload.get("data") is None:
        raise RuntimeError(f"{operation} failed (HTTP {response.status_code}, code={payload.get('code')})")
    return payload["data"]


def _optional_data(response: httpx.Response) -> Any | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if response.status_code >= 400 or not isinstance(payload, dict) or payload.get("code") != 200:
        return None
    return payload.get("data")


def _payload(response: httpx.Response, operation: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{operation} returned a non-JSON response") from exc
    if response.status_code >= 400 or not isinstance(payload, dict):
        raise RuntimeError(f"{operation} failed (HTTP {response.status_code})")
    return payload


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Required environment variable is missing: {name}")
    return value


if __name__ == "__main__":
    main()
