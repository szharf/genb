import json

import httpx

from .identity import CallerIdentity, IdentityVerifier


class GenBTokenIdentityVerifier(IdentityVerifier):
    """Validate service credentials through the protected GenB introspection Interface."""

    def __init__(
        self,
        *,
        client: httpx.Client,
        introspection_url: str,
        internal_token: str,
    ) -> None:
        if len(internal_token) < 16:
            raise ValueError("GenB internal token must contain at least 16 characters")
        self._client = client
        self._introspection_url = introspection_url
        self._internal_token = internal_token

    def verify(self, bearer_token: str) -> CallerIdentity | None:
        try:
            response = self._client.post(
                self._introspection_url,
                headers={
                    "Authorization": f"Bearer {self._internal_token}",
                    "X-Agent-Credential": bearer_token,
                },
            )
            if response.status_code != 200 or len(response.content) > 16_384:
                return None
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("active") is not True:
                return None
            credential_id = payload.get("credentialId")
            agent_id = payload.get("agentId")
            scopes = payload.get("scopes")
            expires_at = payload.get("expiresAt")
            credential_version = payload.get("credentialVersion")
            if not (
                isinstance(credential_id, str)
                and credential_id
                and isinstance(agent_id, str)
                and agent_id
                and isinstance(scopes, list)
                and all(isinstance(scope, str) and scope for scope in scopes)
                and isinstance(expires_at, str)
                and expires_at
                and isinstance(credential_version, int)
                and credential_version >= 0
            ):
                return None
            return CallerIdentity(
                token_id=credential_id,
                scopes=frozenset(scopes),
            )
        except (httpx.HTTPError, TypeError, ValueError, json.JSONDecodeError):
            return None

