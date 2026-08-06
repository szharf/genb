from long_term_memory.main import configured_extraction_model, configured_repository
from long_term_memory.repository import InMemoryConversationMemoryRepository


def test_bootstrap_uses_in_memory_repository_when_postgres_is_not_configured(
    monkeypatch,
) -> None:
    monkeypatch.delenv("LONG_TERM_MEMORY_POSTGRES_DSN", raising=False)

    repository = configured_repository()

    assert isinstance(repository, InMemoryConversationMemoryRepository)
    assert repository.health() is True


def test_bootstrap_does_not_fake_an_extraction_model_without_runtime_token(
    monkeypatch,
) -> None:
    monkeypatch.delenv("LONG_TERM_MEMORY_RUNTIME_TOKEN", raising=False)

    assert configured_extraction_model() is None
