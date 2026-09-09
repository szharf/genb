from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ExchangedSubject:
    session_grant: str
    tenant_id: str
    user_id: str
    username: str
    agent_id: str
    session_id: str


class FakeControlPlane:
    def __init__(self) -> None:
        self._codes: dict[str, dict] = {}
        self.revocations: list[tuple[str, str]] = []

    def add_code(self, *, code: str, state: str | None, agent_id: str, tenant_id: str, user_id: str,
                 username: str, session_grant: str) -> None:
        self._codes[code] = dict(state=state, agent_id=agent_id, tenant_id=tenant_id, user_id=user_id,
                                 username=username, session_grant=session_grant)

    def bind_state(self, code: str, state: str) -> None:
        self._codes[code]["state"] = state

    def exchange(self, *, code: str, state: str, agent_id: str, callback_url: str, session_id: str) -> ExchangedSubject:
        record = self._codes.pop(code, None)
        if not record or record["state"] not in {None, state} or record["agent_id"] != agent_id:
            raise PermissionError("authorization code rejected")
        return ExchangedSubject(record["session_grant"], record["tenant_id"], str(record["user_id"]),
                                record["username"], agent_id, session_id)

    def revoke(self, agent_id: str, session_grant: str) -> None:
        self.revocations.append((agent_id, session_grant))


class HttpControlPlane:
    def __init__(self, base_url: str, machine_token: str, *, timeout: float = 2.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.machine_token = machine_token
        self.timeout = timeout

    def exchange(self, *, code: str, state: str, agent_id: str, callback_url: str, session_id: str) -> ExchangedSubject:
        value = self._post("/api/v1/internal/data-plane/identity/exchange", {
            "schemaVersion": "1.0", "code": code, "agentId": agent_id,
            "callbackUrl": callback_url, "state": state, "sessionId": session_id,
        })
        return ExchangedSubject(
            value["sessionGrant"], value["tenantId"], str(value["userId"]), value["username"],
            value["agentId"], value["sessionId"],
        )

    def revoke(self, agent_id: str, session_grant: str) -> None:
        self._post("/api/v1/internal/data-plane/identity/revoke", {
            "schemaVersion": "1.0", "agentId": agent_id, "sessionGrant": session_grant,
        })

    def issue_actor_token(self, session, capability_code: str) -> str:
        return self.issue_actor_token_lease(session, capability_code).token

    def issue_actor_token_lease(self, session, capability_code: str):
        from .tokens import ActorTokenLease
        value = self._post("/api/v1/internal/data-plane/actor-token", {
            "schemaVersion": "1.0", "sessionGrant": session.session_grant,
            "agentId": session.agent_id, "sessionId": session.session_id,
            "capabilityCode": capability_code,
        })
        token = value.get("actorToken")
        binding_version = value.get("bindingVersion")
        try: expires_at = datetime.fromisoformat(value["expiresAt"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError) as error:
            raise ConnectionError("control plane returned an invalid actor token") from error
        if (value.get("schemaVersion") != "1.0" or value.get("capabilityCode") != capability_code
                or not isinstance(token, str) or not token or not isinstance(binding_version, int)):
            raise ConnectionError("control plane returned an invalid actor token")
        return ActorTokenLease(token, expires_at, binding_version)

    def get_version(self) -> int:
        value = self._get("/api/v1/internal/data-plane/config/version")
        version = value.get("configVersion")
        if value.get("schemaVersion") not in {"1.0", "1.1"} or type(version) is not int or version < 1:
            raise ConnectionError("control plane returned an invalid config version")
        return version

    def get_snapshot(self) -> dict:
        value = self._get("/api/v1/internal/data-plane/config/snapshot")
        if value.get("schemaVersion") not in {"1.0", "1.1"} or type(value.get("configVersion")) is not int:
            raise ConnectionError("control plane returned an invalid config snapshot")
        return value

    def acknowledge(self, version: int) -> None:
        self._post("/api/v1/internal/data-plane/config/applied", {"configVersion": version})

    def append_audits(self, events: list[dict]) -> int:
        value = self._post("/api/v1/internal/data-plane/audits:batch", {
            "schemaVersion":"1.0", "events":events,
        })
        accepted = value.get("accepted")
        if value.get("schemaVersion") != "1.0" or not isinstance(accepted, int):
            raise ConnectionError("control plane returned an invalid audit acknowledgement")
        return accepted

    def _post(self, path: str, value: dict) -> dict:
        request = Request(self.base_url + path, method="POST", data=json.dumps(value).encode(), headers={
            "Authorization": "Bearer " + self.machine_token, "Content-Type": "application/json",
        })
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                return json.loads(body) if body else {}
        except HTTPError as error:
            if 400 <= error.code < 500:
                raise PermissionError("control plane rejected gateway request") from error
            raise ConnectionError("control plane unavailable") from error
        except URLError as error:
            raise ConnectionError("control plane unavailable") from error

    def _get(self, path: str) -> dict:
        request = Request(self.base_url + path, method="GET", headers={
            "Authorization": "Bearer " + self.machine_token, "Accept": "application/json",
        })
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except (HTTPError, URLError, json.JSONDecodeError) as error:
            raise ConnectionError("control plane unavailable") from error


class ControlPlaneActorTokenProvider:
    def __init__(self, control_plane: HttpControlPlane) -> None:
        self.control_plane = control_plane

    def issue(self, session, capability_code: str, binding_version: int = 1) -> str:
        return self.control_plane.issue_actor_token(session, capability_code)

    def issue_lease(self, session, capability_code: str):
        return self.control_plane.issue_actor_token_lease(session, capability_code)
