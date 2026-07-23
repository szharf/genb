import base64
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .errors import AuthenticationProblem, AuthorizationProblem


@dataclass(frozen=True)
class InvocationIdentity:
    tenant_id: str
    user_id: str
    agent_id: str
    session_id: str | None
    service_credential_id: str
    allowed_components: frozenset[str]
    scopes: frozenset[str]
    request_id: str


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


@dataclass(frozen=True)
class ServiceCredential:
    credential_id: str
    agent_id: str
    scopes: frozenset[str]


class ServiceCredentialIntrospector(Protocol):
    def introspect(self, token: str) -> ServiceCredential | None: ...


class StaticServiceCredentialIntrospector:
    def __init__(self, *, credentials: dict[str, ServiceCredential]) -> None:
        self._credentials = credentials

    def introspect(self, token: str) -> ServiceCredential | None:
        return self._credentials.get(token)


@dataclass(frozen=True)
class ActorIdentity:
    tenant_id: str
    user_id: str
    agent_id: str
    session_id: str
    allowed_components: frozenset[str]


class ActorTokenVerifier(Protocol):
    def verify(self, token: str) -> ActorIdentity | None: ...


class RsaActorTokenVerifier:
    def __init__(
        self,
        *,
        public_key_pem: bytes,
        issuer: str,
        audience: str,
        leeway_seconds: int = 30,
    ) -> None:
        public_key = serialization.load_pem_public_key(public_key_pem)
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError("Actor Token public key must be RSA")
        self._public_key = public_key
        self._issuer = issuer
        self._audience = audience
        self._leeway_seconds = leeway_seconds

    def verify(self, token: str) -> ActorIdentity | None:
        try:
            encoded_header, encoded_claims, encoded_signature = token.split(".")
            header = json.loads(_decode_segment(encoded_header))
            claims = json.loads(_decode_segment(encoded_claims))
            if header != {"alg": "RS256", "typ": "JWT"}:
                return None
            self._public_key.verify(
                _decode_bytes(encoded_signature),
                f"{encoded_header}.{encoded_claims}".encode("ascii"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            if not self._claims_are_valid(claims):
                return None
            return ActorIdentity(
                tenant_id=claims["tenantId"],
                user_id=claims["userId"],
                agent_id=claims["agentId"],
                session_id=claims["sessionId"],
                allowed_components=frozenset(claims["components"]),
            )
        except (
            InvalidSignature,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return None

    def _claims_are_valid(self, claims: dict[str, object]) -> bool:
        now = datetime.now(UTC).timestamp()
        audience = claims.get("aud")
        audience_matches = (
            audience == self._audience
            or isinstance(audience, list)
            and self._audience in audience
        )
        identity_fields = [
            claims.get("tenantId"),
            claims.get("userId"),
            claims.get("agentId"),
            claims.get("sessionId"),
        ]
        components = claims.get("components")
        return bool(
            claims.get("iss") == self._issuer
            and audience_matches
            and isinstance(claims.get("exp"), (int, float))
            and now <= float(claims["exp"]) + self._leeway_seconds
            and isinstance(claims.get("nbf"), (int, float))
            and now + self._leeway_seconds >= float(claims["nbf"])
            and all(isinstance(value, str) and value for value in identity_fields)
            and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", str(claims["sessionId"]))
            and isinstance(components, list)
            and all(isinstance(value, str) and value for value in components)
        )


class CompositeIdentityVerifier:
    def __init__(
        self,
        *,
        service_credentials: ServiceCredentialIntrospector,
        actor_tokens: ActorTokenVerifier,
    ) -> None:
        self._service_credentials = service_credentials
        self._actor_tokens = actor_tokens

    def verify(
        self,
        *,
        service_token: str,
        actor_token: str,
        required_component: str,
        required_scope: str,
        request_id: str,
    ) -> InvocationIdentity:
        credential = self._service_credentials.introspect(service_token)
        actor = self._actor_tokens.verify(actor_token)
        if credential is None or actor is None:
            raise AuthenticationProblem("Both credentials must be valid", request_id)
        if credential.agent_id != actor.agent_id:
            raise AuthorizationProblem("Credential and Actor Token do not match", request_id)
        if required_component not in actor.allowed_components:
            raise AuthorizationProblem("Required component is not allowed", request_id)
        if required_scope not in credential.scopes:
            raise AuthorizationProblem("Required scope is missing", request_id)
        return InvocationIdentity(
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            agent_id=actor.agent_id,
            session_id=actor.session_id,
            service_credential_id=credential.credential_id,
            allowed_components=actor.allowed_components,
            scopes=credential.scopes,
            request_id=request_id,
        )


class StaticIdentityVerifier:
    """Test adapter that still requires both credentials and all policy checks."""

    def __init__(
        self,
        *,
        credentials: dict[tuple[str, str], InvocationIdentity],
    ) -> None:
        self._credentials = credentials

    def verify(
        self,
        *,
        service_token: str,
        actor_token: str,
        required_component: str,
        required_scope: str,
        request_id: str,
    ) -> InvocationIdentity:
        identity = self._credentials.get((service_token, actor_token))
        if identity is None:
            raise AuthenticationProblem("Both credentials must be valid", request_id)
        if required_component not in identity.allowed_components:
            raise AuthorizationProblem("Required component is not allowed", request_id)
        if required_scope not in identity.scopes:
            raise AuthorizationProblem("Required scope is missing", request_id)
        return replace(identity, request_id=request_id)


def _decode_segment(value: str) -> str:
    return _decode_bytes(value).decode("utf-8")


def _decode_bytes(value: str) -> bytes:
    padding_length = (-len(value)) % 4
    return base64.urlsafe_b64decode(value + "=" * padding_length)
