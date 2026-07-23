from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote

import httpx

from .errors import RemoteCallError
from .models import (
    ActorSession,
    CommitResult,
    ComponentEndpoint,
    ContextMessage,
    PreparedContext,
)


class GenBClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def issue_component_session(
        self,
        *,
        user_token: str,
        service_credential: str,
        agent_id: str,
        session_id: str,
        requested_components: Sequence[str],
    ) -> ActorSession:
        response = await _post(
            self._client,
            f"{self._base_url}/v1/client/agents/{quote(agent_id, safe='')}/component-session",
            operation="issue component session",
            request_id=None,
            headers={
                "Authorization": f"Bearer {user_token}",
                "X-Agent-Credential": service_credential,
            },
            json={
                "sessionId": session_id,
                "requestedComponents": list(requested_components),
            },
        )
        payload = _object(response, "issue component session", None)
        data = _required_object(payload, "data")
        component_items = data.get("components")
        if not isinstance(component_items, list):
            raise _invalid_payload("issue component session", None)
        components = tuple(_component(item) for item in component_items)
        return ActorSession(
            component_session_id=_required_string(data, "componentSessionId"),
            actor_token=_required_string(data, "actorToken"),
            expires_at=_required_string(data, "expiresAt"),
            components=components,
        )


class ControlSystemClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def prepare_context(
        self,
        *,
        service_credential: str,
        actor_token: str,
        query: str,
        max_context_tokens: int,
        request_id: str,
    ) -> PreparedContext:
        response = await _post(
            self._client,
            f"{self._base_url}/api/v1/control-system/short-term-memory/context:prepare",
            operation="prepare context",
            request_id=request_id,
            headers=_identity_headers(service_credential, actor_token, request_id),
            json={"query": query, "maxContextTokens": max_context_tokens},
        )
        payload = _object(response, "prepare context", request_id)
        data = _required_object(payload, "data")
        raw_messages = data.get("messages")
        if not isinstance(raw_messages, list):
            raise _invalid_payload("prepare context", request_id)
        messages = tuple(
            ContextMessage(
                role=_required_string(_as_mapping(item), "role"),
                content=_required_string(_as_mapping(item), "content"),
                turn_id=_optional_string(_as_mapping(item), "turnId"),
            )
            for item in raw_messages
        )
        meta = payload.get("meta")
        response_request_id = meta.get("requestId") if isinstance(meta, dict) else None
        return PreparedContext(
            messages=messages,
            request_id=response_request_id if isinstance(response_request_id, str) else request_id,
        )

    async def commit_turn(
        self,
        *,
        service_credential: str,
        actor_token: str,
        turn_id: str,
        user_message: str,
        assistant_message: str,
        occurred_at: str,
        request_id: str,
        idempotency_key: str,
    ) -> CommitResult:
        headers = _identity_headers(service_credential, actor_token, request_id)
        headers["Idempotency-Key"] = idempotency_key
        response = await _post(
            self._client,
            f"{self._base_url}/api/v1/control-system/short-term-memory/turns:commit",
            operation="commit turn",
            request_id=request_id,
            headers=headers,
            json={
                "turnId": turn_id,
                "userMessage": user_message,
                "assistantMessage": assistant_message,
                "occurredAt": occurred_at,
            },
        )
        data = _required_object(_object(response, "commit turn", request_id), "data")
        duplicate = data.get("duplicate")
        message_count = data.get("messageCount")
        if not isinstance(duplicate, bool) or not isinstance(message_count, int):
            raise _invalid_payload("commit turn", request_id)
        return CommitResult(
            turn_id=_required_string(data, "turnId"),
            duplicate=duplicate,
            message_count=message_count,
        )

    async def clear_session(
        self,
        *,
        service_credential: str,
        actor_token: str,
        session_id: str,
        request_id: str,
    ) -> bool:
        try:
            response = await self._client.delete(
                f"{self._base_url}/api/v1/control-system/short-term-memory/sessions/"
                f"{quote(session_id, safe='')}",
                headers=_identity_headers(service_credential, actor_token, request_id),
            )
        except httpx.HTTPError as exc:
            raise RemoteCallError(
                operation="clear session", status_code=None, request_id=request_id
            ) from exc
        _raise_for_status(response, "clear session", request_id)
        data = _required_object(_object(response, "clear session", request_id), "data")
        cleared = data.get("cleared")
        if not isinstance(cleared, bool):
            raise _invalid_payload("clear session", request_id)
        return cleared


async def _post(
    client: httpx.AsyncClient,
    url: str,
    *,
    operation: str,
    request_id: str | None,
    headers: Mapping[str, str],
    json: object,
) -> httpx.Response:
    try:
        response = await client.post(url, headers=headers, json=json)
    except httpx.HTTPError as exc:
        raise RemoteCallError(
            operation=operation, status_code=None, request_id=request_id
        ) from exc
    _raise_for_status(response, operation, request_id)
    return response


def _raise_for_status(
    response: httpx.Response, operation: str, request_id: str | None
) -> None:
    if 200 <= response.status_code < 300:
        return
    upstream_request_id = response.headers.get("X-Request-Id") or request_id
    raise RemoteCallError(
        operation=operation,
        status_code=response.status_code,
        request_id=upstream_request_id,
    )


def _object(
    response: httpx.Response, operation: str, request_id: str | None
) -> Mapping[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise _invalid_payload(operation, request_id) from exc
    if not isinstance(payload, dict):
        raise _invalid_payload(operation, request_id)
    return payload


def _component(value: object) -> ComponentEndpoint:
    item = _as_mapping(value)
    config_version_id = item.get("configVersionId")
    scopes = item.get("scopes")
    if not isinstance(config_version_id, int) or not (
        isinstance(scopes, list) and all(isinstance(scope, str) for scope in scopes)
    ):
        raise _invalid_payload("issue component session", None)
    return ComponentEndpoint(
        component_code=_required_string(item, "componentCode"),
        implementation_code=_required_string(item, "implementationCode"),
        base_url=_required_string(item, "baseUrl"),
        interface_version=_required_string(item, "interfaceVersion"),
        config_version_id=config_version_id,
        scopes=tuple(scopes),
    )


def _as_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise _invalid_payload("parse upstream response", None)
    return value


def _required_object(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise _invalid_payload("parse upstream response", None)
    return item


def _required_string(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise _invalid_payload("parse upstream response", None)
    return item


def _optional_string(value: Mapping[str, Any], key: str) -> str | None:
    item = value.get(key)
    return item if isinstance(item, str) else None


def _invalid_payload(operation: str, request_id: str | None) -> RemoteCallError:
    return RemoteCallError(operation=operation, status_code=502, request_id=request_id)


def _identity_headers(
    service_credential: str, actor_token: str, request_id: str
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {service_credential}",
        "X-GenB-Actor-Token": actor_token,
        "X-Request-Id": request_id,
    }
