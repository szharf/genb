import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


@dataclass(frozen=True)
class InvocationIdentity:
    tenant_id: str
    agent_id: str
    user_id: str
    session_id: str
    token_type: str


class IdentityProblem(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class IdentityVerifier(Protocol):
    def verify(
        self,
        *,
        service_token: str,
        actor_token: str,
        required_component: str,
        required_scope: str,
        request_id: str,
    ) -> InvocationIdentity: ...


class DevelopmentHeaderIdentityVerifier:
    def verify_headers(
        self, *, tenant_id: str, agent_id: str, user_id: str
    ) -> InvocationIdentity:
        if not tenant_id or not agent_id or not user_id:
            raise IdentityProblem(401, "开发身份Header不完整")
        return InvocationIdentity(
            tenant_id, agent_id, user_id, "development", "DEVELOPMENT"
        )


class GenBIdentityVerifier:
    def __init__(
        self,
        *,
        client: httpx.Client,
        jwks_url: str,
        introspection_url: str,
        internal_token: str,
        issuer: str = "genb",
        audience: str = "control-system",
    ) -> None:
        if len(internal_token) < 16:
            raise ValueError("GenB internal token must contain at least 16 characters")
        self._client = client
        self._jwks_url = jwks_url
        self._introspection_url = introspection_url
        self._internal_token = internal_token
        self._issuer = issuer
        self._audience = audience

    def verify(
        self,
        *,
        service_token: str,
        actor_token: str,
        required_component: str,
        required_scope: str,
        request_id: str,
    ) -> InvocationIdentity:
        claims = self._verify_actor(actor_token)
        if claims is None:
            raise IdentityProblem(401, "Actor Token无效")
        components = claims.get("components")
        scopes = claims.get("scopes")
        if required_component not in components or required_scope not in scopes:
            raise IdentityProblem(403, "组件或操作权限不足")
        token_type = claims["tokenType"]
        if token_type == "COMPONENT_SESSION":
            credential = self._introspect(service_token)
            if credential is None:
                raise IdentityProblem(401, "服务凭证无效")
            if credential.get("agentId") != claims["agentId"]:
                raise IdentityProblem(403, "服务凭证与智能体不匹配")
        elif token_type == "COMPONENT_ADMIN_TEST":
            if service_token:
                raise IdentityProblem(400, "管理员服务直测不接收智能体服务凭证")
        else:
            raise IdentityProblem(401, "Actor Token类型无效")
        return InvocationIdentity(
            tenant_id=claims["tenantId"],
            agent_id=claims["agentId"],
            user_id=claims["userId"],
            session_id=claims["sessionId"],
            token_type=token_type,
        )

    def _introspect(self, service_token: str) -> dict[str, object] | None:
        if not service_token:
            return None
        try:
            response = self._client.post(
                self._introspection_url,
                headers={
                    "Authorization": f"Bearer {self._internal_token}",
                    "X-Agent-Credential": service_token,
                },
            )
            payload = response.json()
            if response.status_code != 200 or payload.get("active") is not True:
                return None
            return payload if isinstance(payload.get("agentId"), str) else None
        except (httpx.HTTPError, ValueError, json.JSONDecodeError):
            return None

    def _verify_actor(self, token: str) -> dict[str, object] | None:
        try:
            encoded_header, encoded_claims, encoded_signature = token.split(".")
            header = json.loads(_decode(encoded_header))
            claims = json.loads(_decode(encoded_claims))
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                return None
            response = self._client.get(
                self._jwks_url, headers={"Accept": "application/json"}
            )
            if response.status_code != 200 or len(response.content) > 65_536:
                return None
            public_key = _select_key(response.json(), header["kid"])
            if public_key is None:
                return None
            public_key.verify(
                _decode_bytes(encoded_signature),
                f"{encoded_header}.{encoded_claims}".encode("ascii"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return claims if self._valid_claims(claims) else None
        except (
            InvalidSignature,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            httpx.HTTPError,
        ):
            return None

    def _valid_claims(self, claims: dict[str, object]) -> bool:
        now = datetime.now(UTC).timestamp()
        audience = claims.get("aud")
        audience_matches = audience == self._audience or (
            isinstance(audience, list) and self._audience in audience
        )
        required_strings = ("tenantId", "agentId", "userId", "sessionId", "tokenType")
        components = claims.get("components")
        scopes = claims.get("scopes")
        return bool(
            claims.get("iss") == self._issuer
            and audience_matches
            and claims.get("sub") == claims.get("userId")
            and all(isinstance(claims.get(key), str) and claims[key] for key in required_strings)
            and isinstance(components, list)
            and all(isinstance(value, str) and value for value in components)
            and isinstance(scopes, list)
            and all(isinstance(value, str) and value for value in scopes)
            and isinstance(claims.get("iat"), (int, float))
            and isinstance(claims.get("nbf"), (int, float))
            and isinstance(claims.get("exp"), (int, float))
            and now + 30 >= float(claims["iat"])
            and now + 30 >= float(claims["nbf"])
            and now <= float(claims["exp"]) + 30
            and 0 < float(claims["exp"]) - float(claims["iat"]) <= 900
        )


def _select_key(payload: object, key_id: str) -> rsa.RSAPublicKey | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        return None
    matches = [
        item
        for item in payload["keys"]
        if isinstance(item, dict) and item.get("kid") == key_id
    ]
    if len(matches) != 1:
        return None
    key = matches[0]
    if key.get("kty") != "RSA" or key.get("alg") != "RS256":
        return None
    modulus = int.from_bytes(_decode_bytes(key["n"]), "big")
    exponent = int.from_bytes(_decode_bytes(key["e"]), "big")
    if modulus.bit_length() < 2048 or exponent < 3:
        return None
    return rsa.RSAPublicNumbers(exponent, modulus).public_key()


def _decode(value: str) -> str:
    return _decode_bytes(value).decode("utf-8")


def _decode_bytes(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * ((-len(value)) % 4))
