from collections.abc import Mapping, Sequence
import re
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
    InferenceResult,
)


class GatewayCapabilityClient:
    """The only 18714 client allowed to invoke published core capabilities."""

    _CAPABILITY = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
    _OPERATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

    def __init__(self, client: httpx.AsyncClient, base_url: str, *, identity_token: str,
                 agent_credential: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._identity_token = identity_token
        self._agent_credential = agent_credential

    async def invoke(self, capability: str, operation: str, payload: object, *, request_id: str,
                     conversation_id: str, idempotency_key: str | None = None) -> dict[str, Any]:
        if not self._CAPABILITY.fullmatch(capability) or not self._OPERATION.fullmatch(operation):
            raise ValueError("invalid capability operation")
        headers = {
            "Authorization": f"Bearer {self._identity_token}",
            "X-GenB-Agent-Credential": self._agent_credential,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        response = await _post(
            self._client,
            f"{self._base_url}/component-api/v1/capabilities/{capability}/operations/{operation}:invoke",
            operation=f"invoke {capability} {operation}", request_id=request_id, headers=headers,
            json={
                "schemaVersion": "1.0",
                "context": {"requestId": request_id, "conversationId": conversation_id},
                "payload": payload,
            },
        )
        return dict(_object(response, f"invoke {capability} {operation}", request_id))


class GatewayBindingClient:
    """Compatibility seam while orchestrators stop resolving component addresses from GenB."""

    def __init__(self, gateway_url: str) -> None:
        self._gateway_url = gateway_url.rstrip("/")

    async def issue_component_session(self, *, requested_components: Sequence[str], session_id: str,
                                      **_ignored) -> ActorSession:
        return ActorSession(
            component_session_id="gateway:" + session_id, actor_token="gateway-managed", expires_at="gateway-managed",
            components=tuple(ComponentEndpoint(
                component_code=code, implementation_code="gateway-published", base_url=self._gateway_url,
                interface_version="1.0.0", config_version_id=1, scopes=(),
            ) for code in requested_components),
        )


class GatewayShortTermMemoryClient:
    def __init__(self, gateway: GatewayCapabilityClient) -> None: self._gateway = gateway

    async def prepare_context(self, *, task_id: str, session_id: str, query: str, request_id: str, **_ignored) -> PreparedContext:
        payload = await self._gateway.invoke(
            "SHORT_TERM_MEMORY", "prepareShortTermContext",
            {"taskId":task_id, "sessionId":session_id, "query":query, "maxMessages":20},
            request_id=request_id, conversation_id=session_id,
        )
        data = _required_object(payload, "data")
        messages = data.get("messages")
        if not isinstance(messages, list): raise _invalid_payload("prepare short-term context", request_id)
        return PreparedContext(tuple(ContextMessage(
            role=_required_string(_as_mapping(item), "role"),
            content=_required_string(_as_mapping(item), "content"),
            turn_id=_optional_string(_as_mapping(item), "turnId"),
        ) for item in messages), request_id)

    async def commit_turn(self, *, task_id: str, session_id: str, turn_id: str, user_message: str,
                          assistant_message: str, occurred_at: str, request_id: str,
                          idempotency_key: str, **_ignored) -> CommitResult:
        payload = await self._gateway.invoke(
            "SHORT_TERM_MEMORY", "commitShortTermTurn", {
                "taskId":task_id, "sessionId":session_id, "turnId":turn_id, "userMessage":user_message,
                "assistantMessage":assistant_message, "occurredAt":occurred_at,
            }, request_id=request_id, conversation_id=session_id, idempotency_key=idempotency_key,
        )
        data = _required_object(payload, "data")
        count = data.get("messageCount"); replayed = data.get("replayed", data.get("duplicate", False))
        if not isinstance(count, int) or not isinstance(replayed, bool):
            raise _invalid_payload("commit short-term turn", request_id)
        return CommitResult(turn_id, replayed, count)


class GatewayLongTermMemoryClient:
    def __init__(self, gateway: GatewayCapabilityClient) -> None: self._gateway = gateway

    async def request_long_term_extraction(self, *, conversation_id: str, turn_id: str, user_message: str,
                                           assistant_message: str, occurred_at: str, request_id: str,
                                           idempotency_key: str, **_ignored) -> str:
        payload = await self._gateway.invoke("LONG_TERM_MEMORY", "createConversationMemoryExtraction", {
            "conversationId":conversation_id, "turnId":turn_id, "userMessage":user_message,
            "assistantMessage":assistant_message, "occurredAt":occurred_at,
        }, request_id=request_id, conversation_id=conversation_id, idempotency_key=idempotency_key)
        return _required_string(_required_object(payload, "data"), "extractionId")

    async def get_long_term_extraction(self, *, extraction_id: str, request_id: str, **_ignored) -> ExtractionStatus:
        payload = await self._gateway.invoke("LONG_TERM_MEMORY", "getLongTermExtraction",
            {"extractionId":extraction_id}, request_id=request_id, conversation_id=extraction_id)
        data = _required_object(payload, "data")
        written, rejected = data.get("writtenCount"), data.get("rejectedCount")
        if not isinstance(written, int) or not isinstance(rejected, int):
            raise _invalid_payload("get long-term extraction", request_id)
        return ExtractionStatus(extraction_id, _required_string(data, "status"), written, rejected)

    async def search_long_term_memory(self, *, query: str, request_id: str, source_types=None,
                                      conversation_id: str = "long-term-search", **_ignored) -> tuple[LongTermMemoryItem, ...]:
        body: dict[str, object] = {"query":query, "topK":10}
        if source_types is not None: body["sourceTypes"] = list(source_types)
        payload = await self._gateway.invoke("LONG_TERM_MEMORY", "searchLongTermMemories", body,
                                             request_id=request_id, conversation_id=conversation_id)
        items = _required_object(payload, "data").get("items")
        if not isinstance(items, list): raise _invalid_payload("search long-term memory", request_id)
        return tuple(LongTermMemoryItem(
            _required_string(_as_mapping(item), "memoryId"), _required_string(_as_mapping(item), "type"),
            _required_string(_as_mapping(item), "content"), float(_as_mapping(item)["confidence"]),
            _required_string(_as_mapping(item), "sourceType"), _required_string(_as_mapping(item), "sourceRef"),
        ) for item in items)


class GatewayPlanningReasoningClient:
    _OPERATIONS = {"ANALYZE":"analyzeRequirement", "CONVERSE":"converseRequirement",
                   "GENERATE":"generateSkill", "VALIDATE":"validateSkill"}
    def __init__(self, gateway: GatewayCapabilityClient) -> None: self._gateway = gateway

    async def invoke(self, *, operation: str, payload: Mapping[str, Any], request_id: str, **_ignored) -> dict[str, Any]:
        normalized = operation.strip().upper()
        operation_id = self._OPERATIONS.get(normalized)
        if operation_id is None: raise ValueError("Unsupported planning operation")
        result = await self._gateway.invoke(
            "PLANNING_REASONING", operation_id, dict(payload), request_id=request_id,
            conversation_id=str(payload.get("sessionId") or request_id),
            idempotency_key=f"idem_{request_id}" if normalized == "GENERATE" else None,
        )
        return dict(_required_object(result, "data"))


class GatewayRuntimeInferenceClient:
    def __init__(self, gateway: GatewayCapabilityClient, model_alias: str = "agent-chat-default") -> None:
        self._gateway, self._model_alias = gateway, model_alias

    async def complete(self, *, messages: Sequence[Mapping[str, str]], request_id: str, **_ignored) -> InferenceResult:
        result = await self._gateway.invoke("INFERENCE_ENGINE", "completeChat", {
            "capability":"AGENT_CHAT", "modelAlias":self._model_alias,
            "messages":[dict(message) for message in messages],
        }, request_id=request_id, conversation_id=request_id)
        data = _required_object(result, "data"); usage = _required_object(data, "usage")
        meta = _required_object(result, "meta")
        return InferenceResult(
            _required_string(data, "content"), _required_string(data, "provider"), _required_string(data, "model"),
            int(usage["inputTokens"]), int(usage["outputTokens"]), _required_string(meta, "requestId"),
        )


class GenBClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def issue_component_session(
        self,
        *,
        user_token: str | None = None,
        session_grant: str | None = None,
        service_credential: str,
        agent_id: str,
        session_id: str,
        requested_components: Sequence[str],
    ) -> ActorSession:
        if bool(user_token) == bool(session_grant):
            raise ValueError("exactly one user_token or session_grant is required")
        identity_header = (
            {"Authorization": f"Bearer {user_token}"}
            if user_token
            else {"X-Agent-Session-Grant": session_grant}
        )
        response = await _post(
            self._client,
            f"{self._base_url}/v1/client/agents/{quote(agent_id, safe='')}/component-session",
            operation="issue component session",
            request_id=None,
            headers={"X-Agent-Credential": service_credential, **identity_header},
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
        base_url: str | None = None,
        conversation_id: str | None = None,
    ) -> str:
        headers = _identity_headers(service_credential, actor_token, request_id)
        headers["Idempotency-Key"] = idempotency_key
        standalone = base_url is not None
        target = (base_url or self._base_url).rstrip("/")
        body = {
            "turnId": turn_id,
            "userMessage": user_message,
            "assistantMessage": assistant_message,
            "occurredAt": occurred_at,
        }
        if standalone:
            if not conversation_id:
                raise ValueError("standalone long-term extraction requires conversation_id")
            body["conversationId"] = conversation_id
        response = await _post(
            self._client,
            (
                f"{target}/api/v1/long-term-memory/extractions"
                if standalone
                else f"{target}/api/v1/control-system/long-term-memory/extractions"
            ),
            operation="request long-term extraction",
            request_id=request_id,
            headers=headers,
            json=body,
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
        base_url: str | None = None,
    ) -> ExtractionStatus:
        standalone = base_url is not None
        target = (base_url or self._base_url).rstrip("/")
        response = await _get(
            self._client,
            (
                f"{target}/api/v1/long-term-memory/extractions/{quote(extraction_id, safe='')}"
                if standalone
                else f"{target}/api/v1/control-system/long-term-memory/extractions/{quote(extraction_id, safe='')}"
            ),
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
        source_types: Sequence[str] | None = None,
        base_url: str | None = None,
    ) -> tuple[LongTermMemoryItem, ...]:
        body: dict[str, object] = {"query": query, "topK": top_k}
        if source_types is not None:
            body["sourceTypes"] = list(source_types)
        standalone = base_url is not None
        target = (base_url or self._base_url).rstrip("/")
        response = await _post(
            self._client,
            (
                f"{target}/api/v1/long-term-memory/memories:search"
                if standalone
                else f"{target}/api/v1/control-system/long-term-memory/search"
            ),
            operation="search long-term memory",
            request_id=request_id,
            headers=_identity_headers(service_credential, actor_token, request_id),
            json=body,
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
                source_type=_required_string(item, "sourceType"),
                source_ref=_required_string(item, "sourceRef"),
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
        base_url: str | None = None,
    ) -> bool:
        standalone = base_url is not None
        target = (base_url or self._base_url).rstrip("/")
        url = (
            f"{target}/api/v1/long-term-memory/memories/{quote(memory_id, safe='')}"
            if standalone
            else f"{target}/api/v1/control-system/long-term-memory/memories/{quote(memory_id, safe='')}:delete"
        )
        try:
            response = await self._client.request(
                "DELETE" if standalone else "POST",
                url,
                headers=_identity_headers(service_credential, actor_token, request_id),
                json={"reason": reason},
            )
        except httpx.HTTPError as exc:
            raise RemoteCallError(
                operation="delete long-term memory",
                status_code=None,
                request_id=request_id,
            ) from exc
        _raise_for_status(response, "delete long-term memory", request_id)
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
            "CONVERSE": "/api/v1/planning-reasoning/requirements:converse",
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


class RuntimeInferenceClient:
    def __init__(self, client: httpx.AsyncClient, model_alias: str = "agent-chat-default") -> None:
        self._client = client
        self._model_alias = model_alias

    async def complete(
        self,
        *,
        base_url: str,
        service_credential: str,
        actor_token: str,
        messages: Sequence[Mapping[str, str]],
        request_id: str,
    ) -> InferenceResult:
        response = await _post(
            self._client,
            f"{base_url.rstrip('/')}/api/v1/runtime-system/inference",
            operation="invoke runtime inference",
            request_id=request_id,
            headers={
                "Authorization": f"Bearer {service_credential}",
                "X-GenB-Actor-Token": actor_token,
                "X-Request-Id": request_id,
            },
            json={
                "capability": "AGENT_CHAT",
                "modelAlias": self._model_alias,
                "messages": [dict(message) for message in messages],
            },
        )
        payload = _object(response, "invoke runtime inference", request_id)
        data = _required_object(payload, "data")
        usage = _required_object(data, "usage")
        input_tokens = usage.get("inputTokens")
        output_tokens = usage.get("outputTokens")
        if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
            raise _invalid_payload("invoke runtime inference", request_id)
        meta = _required_object(payload, "meta")
        return InferenceResult(
            content=_required_string(data, "content"),
            provider=_required_string(data, "provider"),
            model=_required_string(data, "model"),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            request_id=_required_string(meta, "requestId"),
        )


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
