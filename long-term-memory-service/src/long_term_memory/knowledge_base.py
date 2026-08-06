from typing import Protocol

from .models import LongTermMemoryRecord


class KnowledgeBaseAdapterProblem(Exception):
    pass


class KnowledgeBaseUnavailable(KnowledgeBaseAdapterProblem):
    pass


class KnowledgeBaseTimeout(KnowledgeBaseAdapterProblem):
    pass


class KnowledgeBasePermissionDenied(KnowledgeBaseAdapterProblem):
    pass


class KnowledgeBaseAccessRevoked(KnowledgeBaseAdapterProblem):
    pass


class KnowledgeBaseAdapter(Protocol):
    def search(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        query: str,
        types: frozenset[str] | None,
        limit: int,
    ) -> list[LongTermMemoryRecord]: ...


class UnavailableKnowledgeBaseAdapter:
    def search(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        query: str,
        types: frozenset[str] | None,
        limit: int,
    ) -> list[LongTermMemoryRecord]:
        del tenant_id, agent_id, user_id, query, types, limit
        raise KnowledgeBaseUnavailable


class FakeKnowledgeBaseAdapter:
    """Contract-test Adapter; it never performs knowledge-base business logic."""

    def __init__(
        self,
        items: list[LongTermMemoryRecord] | None = None,
        *,
        problem: type[KnowledgeBaseAdapterProblem] | None = None,
    ) -> None:
        self._items = list(items or [])
        self._problem = problem
        self.calls: list[dict[str, object]] = []

    def search(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        query: str,
        types: frozenset[str] | None,
        limit: int,
    ) -> list[LongTermMemoryRecord]:
        self.calls.append(
            {
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "user_id": user_id,
                "query": query,
                "types": types,
                "limit": limit,
            }
        )
        if self._problem is not None:
            raise self._problem
        return self._items[:limit]
