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
    component_config_versions: tuple[tuple[str, int], ...] = ()
    trace_parent: str | None = None

    def config_version_for(self, component_code: str) -> int | None:
        return dict(self.component_config_versions).get(component_code)


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
    component_config_versions: tuple[tuple[str, int], ...] = ()


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
        return _verify_rsa_actor_token(
            token,
            public_key=self._public_key,
            issuer=self._issuer,
            audience=self._audience,
            leeway_seconds=self._leeway_seconds,
        )


def _verify_rsa_actor_token(
    token: str,
    *,
    public_key: rsa.RSAPublicKey,
    issuer: str,
    audience: str,
    leeway_seconds: int,
) -> ActorIdentity | None:
    try:
        encoded_header, encoded_claims, encoded_signature = token.split(".")
        header = json.loads(_decode_segment(encoded_header))
        claims = json.loads(_decode_segment(encoded_claims))
        if not (
            isinstance(header, dict)
            and isinstance(claims, dict)
            and header.get("alg") == "RS256"
            and header.get("typ") in {None, "JWT"}
        ):
            return None
        public_key.verify(
            _decode_bytes(encoded_signature),
            f"{encoded_header}.{encoded_claims}".encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        if not _claims_are_valid(
            claims,
            issuer=issuer,
            audience=audience,
            leeway_seconds=leeway_seconds,
        ):
            return None
        return ActorIdentity(
            tenant_id=claims["tenantId"],
            user_id=claims["userId"],
            agent_id=claims["agentId"],
            session_id=claims["sessionId"],
            allowed_components=frozenset(claims["components"]),
            component_config_versions=_parse_component_config_versions(claims),
        )
    except (
        InvalidSignature,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return None


def _claims_are_valid(
    claims: dict[str, object],
    *,
    issuer: str,
    audience: str,
    leeway_seconds: int,
) -> bool:
    now = datetime.now(UTC).timestamp()
    token_audience = claims.get("aud")
    audience_matches = (
        token_audience == audience
        or isinstance(token_audience, list)
        and audience in token_audience
    )
    identity_fields = [
        claims.get("tenantId"),
        claims.get("userId"),
        claims.get("agentId"),
        claims.get("sessionId"),
    ]
    components = claims.get("components")
    return bool(
        claims.get("iss") == issuer
        and audience_matches
        and claims.get("sub") == claims.get("userId")
        and isinstance(claims.get("iat"), (int, float))
        and now + leeway_seconds >= float(claims["iat"])
        and isinstance(claims.get("exp"), (int, float))
        and now <= float(claims["exp"]) + leeway_seconds
        and isinstance(claims.get("nbf"), (int, float))
        and now + leeway_seconds >= float(claims["nbf"])
        and float(claims["exp"]) >= float(claims["nbf"])
        and 0 < float(claims["exp"]) - float(claims["iat"]) <= 900
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
            component_config_versions=actor.component_config_versions,
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


def _parse_component_config_versions(
    claims: dict[str, object],
) -> tuple[tuple[str, int], ...]:
    snapshot = claims.get("bindingSnapshot")
    if snapshot is None:
        return ()
    if not isinstance(snapshot, list):
        raise ValueError("bindingSnapshot must be an array")
    versions: dict[str, int] = {}
    for item in snapshot:
        if not isinstance(item, dict):
            raise ValueError("bindingSnapshot entry must be an object")
        component_code = item.get("componentCode")
        config_id = item.get("configVersionId")
        if not (
            isinstance(component_code, str)
            and component_code
            and isinstance(config_id, int)
            and not isinstance(config_id, bool)
            and config_id > 0
            and component_code not in versions
        ):
            raise ValueError("bindingSnapshot entry is invalid")
        versions[component_code] = config_id
    return tuple(sorted(versions.items()))


def _decode_bytes(value: str) -> bytes:
    padding_length = (-len(value)) % 4
    return base64.urlsafe_b64decode(value + "=" * padding_length)
