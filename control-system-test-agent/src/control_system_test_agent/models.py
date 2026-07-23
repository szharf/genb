from dataclasses import dataclass


@dataclass(frozen=True)
class ComponentEndpoint:
    component_code: str
    implementation_code: str
    base_url: str
    interface_version: str
    config_version_id: int
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class ActorSession:
    component_session_id: str
    actor_token: str
    expires_at: str
    components: tuple[ComponentEndpoint, ...]


@dataclass(frozen=True)
class ContextMessage:
    role: str
    content: str
    turn_id: str | None = None


@dataclass(frozen=True)
class PreparedContext:
    messages: tuple[ContextMessage, ...]
    request_id: str | None


@dataclass(frozen=True)
class CommitResult:
    turn_id: str
    duplicate: bool
    message_count: int


@dataclass(frozen=True)
class ChatResult:
    answer: str
    context_message_count: int
    committed: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ExtractionStatus:
    extraction_id: str
    status: str
    written_count: int
    rejected_count: int


@dataclass(frozen=True)
class LongTermMemoryItem:
    memory_id: str
    memory_type: str
    content: str
    confidence: float
