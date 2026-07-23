import base64
import json

import httpx
from cryptography.hazmat.primitives.asymmetric import rsa

from .identity import (
    ActorIdentity,
    ActorTokenVerifier,
    ServiceCredential,
    ServiceCredentialIntrospector,
    _verify_rsa_actor_token,
)


class GenBServiceCredentialIntrospector(ServiceCredentialIntrospector):
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

    def introspect(self, token: str) -> ServiceCredential | None:
        try:
            response = self._client.post(
                self._introspection_url,
                headers={
                    "Authorization": f"Bearer {self._internal_token}",
                    "X-Agent-Credential": token,
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
            return ServiceCredential(
                credential_id=credential_id,
                agent_id=agent_id,
                scopes=frozenset(scopes),
            )
        except (httpx.HTTPError, TypeError, ValueError, json.JSONDecodeError):
            return None


class GenBJwksActorTokenVerifier(ActorTokenVerifier):
    def __init__(
        self,
        *,
        client: httpx.Client,
        jwks_url: str,
        issuer: str,
        audience: str,
        leeway_seconds: int = 30,
    ) -> None:
        self._client = client
        self._jwks_url = jwks_url
        self._issuer = issuer
        self._audience = audience
        self._leeway_seconds = leeway_seconds

    def verify(self, token: str) -> ActorIdentity | None:
        try:
            encoded_header = token.split(".")[0]
            header = json.loads(_decode_segment(encoded_header))
            if not isinstance(header, dict):
                return None
            key_id = header.get("kid")
            if header.get("alg") != "RS256" or not isinstance(key_id, str):
                return None
            response = self._client.get(
                self._jwks_url,
                headers={"Accept": "application/json"},
            )
            if response.status_code != 200 or len(response.content) > 65_536:
                return None
            public_key = _select_public_key(response.json(), key_id)
            if public_key is None:
                return None
            return _verify_rsa_actor_token(
                token,
                public_key=public_key,
                issuer=self._issuer,
                audience=self._audience,
                leeway_seconds=self._leeway_seconds,
            )
        except (httpx.HTTPError, TypeError, ValueError, json.JSONDecodeError):
            return None


def _select_public_key(payload: object, key_id: str) -> rsa.RSAPublicKey | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        return None
    matches = [
        key
        for key in payload["keys"]
        if isinstance(key, dict) and key.get("kid") == key_id
    ]
    if len(matches) != 1:
        return None
    key = matches[0]
    if not (
        key.get("kty") == "RSA"
        and key.get("use") == "sig"
        and key.get("alg") == "RS256"
        and isinstance(key.get("n"), str)
        and isinstance(key.get("e"), str)
    ):
        return None
    modulus = int.from_bytes(_decode_bytes(key["n"]), "big")
    exponent = int.from_bytes(_decode_bytes(key["e"]), "big")
    if modulus.bit_length() < 2048 or exponent < 3:
        return None
    return rsa.RSAPublicNumbers(exponent, modulus).public_key()


def _decode_segment(value: str) -> str:
    return _decode_bytes(value).decode("utf-8")


def _decode_bytes(value: str) -> bytes:
    padding_length = (-len(value)) % 4
    return base64.urlsafe_b64decode(value + "=" * padding_length)
