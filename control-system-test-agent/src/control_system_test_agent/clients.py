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
    ExtractionStatus,
    LongTermMemoryItem,
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

    async def request_long_term_extraction(
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
    ) -> str:
        headers = _identity_headers(service_credential, actor_token, request_id)
        headers["Idempotency-Key"] = idempotency_key
        response = await _post(
            self._client,
            f"{self._base_url}/api/v1/control-system/long-term-memory/extractions",
            operation="request long-term extraction",
            request_id=request_id,
            headers=headers,
            json={
                "turnId": turn_id,
                "userMessage": user_message,
                "assistantMessage": assistant_message,
                "occurredAt": occurred_at,
            },
        )
        data = _required_object(_object(response, "request long-term extraction", request_id), "data")
        return _required_string(data, "extractionId")

    async def get_long_term_extraction(
        self,
        *,
        service_credential: str,
        actor_token: str,
        extraction_id: str,
        request_id: str,
    ) -> ExtractionStatus:
        response = await _get(
            self._client,
            f"{self._base_url}/api/v1/control-system/long-term-memory/extractions/{quote(extraction_id, safe='')}",
            operation="get long-term extraction",
            request_id=request_id,
            headers=_identity_headers(service_credential, actor_token, request_id),
        )
        data = _required_object(_object(response, "get long-term extraction", request_id), "data")
        written = data.get("writtenCount")
        rejected = data.get("rejectedCount")
        if not isinstance(written, int) or not isinstance(rejected, int):
            raise _invalid_payload("get long-term extraction", request_id)
        return ExtractionStatus(
            extraction_id=_required_string(data, "extractionId"),
            status=_required_string(data, "status"),
            written_count=written,
            rejected_count=rejected,
        )

    async def search_long_term_memory(
        self,
        *,
        service_credential: str,
        actor_token: str,
        query: str,
        request_id: str,
        top_k: int = 10,
    ) -> tuple[LongTermMemoryItem, ...]:
        response = await _post(
            self._client,
            f"{self._base_url}/api/v1/control-system/long-term-memory/search",
            operation="search long-term memory",
            request_id=request_id,
            headers=_identity_headers(service_credential, actor_token, request_id),
            json={"query": query, "topK": top_k},
        )
        data = _required_object(_object(response, "search long-term memory", request_id), "data")
        raw_items = data.get("items")
        if not isinstance(raw_items, list):
            raise _invalid_payload("search long-term memory", request_id)
        items: list[LongTermMemoryItem] = []
        for raw in raw_items:
            item = _as_mapping(raw)
            confidence = item.get("confidence")
            if not isinstance(confidence, (int, float)):
                raise _invalid_payload("search long-term memory", request_id)
            items.append(LongTermMemoryItem(
                memory_id=_required_string(item, "memoryId"),
                memory_type=_required_string(item, "type"),
                content=_required_string(item, "content"),
                confidence=float(confidence),
            ))
        return tuple(items)

    async def delete_long_term_memory(
        self,
        *,
        service_credential: str,
        actor_token: str,
        memory_id: str,
        reason: str,
        request_id: str,
    ) -> bool:
        response = await _post(
            self._client,
            f"{self._base_url}/api/v1/control-system/long-term-memory/memories/{quote(memory_id, safe='')}:delete",
            operation="delete long-term memory",
            request_id=request_id,
            headers=_identity_headers(service_credential, actor_token, request_id),
            json={"reason": reason},
        )
        data = _required_object(_object(response, "delete long-term memory", request_id), "data")
        deleted = data.get("deleted")
        if not isinstance(deleted, bool):
            raise _invalid_payload("delete long-term memory", request_id)
        return deleted


class StandaloneShortTermMemoryClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def prepare_context(
        self,
        *,
        base_url: str,
        service_credential: str,
        actor_token: str,
        task_id: str,
        session_id: str,
        query: str,
        request_id: str,
    ) -> PreparedContext:
        response = await _post(
            self._client,
            f"{base_url.rstrip('/')}/api/v1/short-term-memory/context:prepare",
            operation="prepare standalone short-term context",
            request_id=request_id,
            headers=_identity_headers(service_credential, actor_token, request_id),
            json={"taskId": task_id, "sessionId": session_id, "query": query, "maxMessages": 20},
        )
        data = _required_object(_object(response, "prepare standalone short-term context", request_id), "data")
        raw_messages = data.get("messages")
        if not isinstance(raw_messages, list):
            raise _invalid_payload("prepare standalone short-term context", request_id)
        return PreparedContext(
            messages=tuple(
                ContextMessage(
                    role=_required_string(_as_mapping(item), "role"),
                    content=_required_string(_as_mapping(item), "content"),
                    turn_id=_optional_string(_as_mapping(item), "turnId"),
                )
                for item in raw_messages
            ),
            request_id=request_id,
        )

    async def commit_turn(
        self,
        *,
        base_url: str,
        service_credential: str,
        actor_token: str,
        task_id: str,
        session_id: str,
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
            f"{base_url.rstrip('/')}/api/v1/short-term-memory/turns:commit",
            operation="commit standalone short-term turn",
            request_id=request_id,
            headers=headers,
            json={
                "taskId": task_id,
                "sessionId": session_id,
                "turnId": turn_id,
                "userMessage": user_message,
                "assistantMessage": assistant_message,
                "occurredAt": occurred_at,
            },
        )
        data = _required_object(_object(response, "commit standalone short-term turn", request_id), "data")
        replayed = data.get("replayed")
        message_count = data.get("messageCount")
        if not isinstance(replayed, bool) or not isinstance(message_count, int):
            raise _invalid_payload("commit standalone short-term turn", request_id)
        return CommitResult(
            turn_id=turn_id,
            duplicate=replayed,
            message_count=message_count,
        )


class PlanningReasoningClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def invoke(
        self,
        *,
        base_url: str,
        service_credential: str,
        actor_token: str,
        operation: str,
        payload: Mapping[str, Any],
        request_id: str,
    ) -> dict[str, Any]:
        normalized = operation.strip().upper()
        paths = {
            "ANALYZE": "/api/v1/planning-reasoning/requirements:analyze",
            "GENERATE": "/api/v1/planning-reasoning/skills:generate",
            "VALIDATE": "/api/v1/planning-reasoning/skills:validate",
        }
        body = dict(payload)
        if normalized == "REVISE":
            skill_id = body.pop("skillId", "")
            if not isinstance(skill_id, str) or not skill_id:
                raise ValueError("REVISE requires skillId")
            path = f"/api/v1/planning-reasoning/skills/{quote(skill_id, safe='')}:revise"
        else:
            path = paths.get(normalized)
            if path is None:
                raise ValueError("Unsupported planning operation")
        headers = _identity_headers(service_credential, actor_token, request_id)
        if normalized in {"GENERATE", "REVISE"}:
            headers["Idempotency-Key"] = f"idem_{request_id}"
        response = await _post(
            self._client,
            f"{base_url.rstrip('/')}{path}",
            operation=f"planning {normalized.lower()}",
            request_id=request_id,
            headers=headers,
            json=body,
        )
        data = _required_object(_object(response, f"planning {normalized.lower()}", request_id), "data")
        return dict(data)


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


async def _get(
    client: httpx.AsyncClient,
    url: str,
    *,
    operation: str,
    request_id: str | None,
    headers: Mapping[str, str],
) -> httpx.Response:
    try:
        response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise RemoteCallError(operation=operation, status_code=None, request_id=request_id) from exc
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
