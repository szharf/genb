from dataclasses import dataclass
from typing import Mapping, Protocol, AbstractSet


@dataclass(frozen=True)
class CallerIdentity:
    token_id: str
    scopes: frozenset[str]


class IdentityVerifier(Protocol):
    def verify(self, bearer_token: str) -> CallerIdentity | None: ...


class StaticTokenIdentityVerifier:
    """Local/test identity Adapter. Production identity will be supplied by GenB."""

    def __init__(self, tokens: Mapping[str, AbstractSet[str]]) -> None:
        self._tokens = {
            token: frozenset(scopes) for token, scopes in tokens.items()
        }

    def verify(self, bearer_token: str) -> CallerIdentity | None:
        scopes = self._tokens.get(bearer_token)
        if scopes is None:
            return None
        return CallerIdentity(token_id=bearer_token, scopes=scopes)
