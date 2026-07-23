import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime

from .models import (
    ConversationSummary,
    ConversationTurn,
    PreparedContext,
    StoreCommitResult,
    StoredMessage,
)
from .redaction import redact_sensitive_content
from .store import (
    IdempotencyConflictError,
    ScopeKey,
    SessionStore,
    StoreUnavailableError,
)
from ..component_config import (
    RuntimeConfigUnavailable,
    ShortTermMemoryConfigProvider,
)
from ..errors import DependencyProblem, IdempotencyProblem, RuntimeConfigProblem
from ..identity import InvocationIdentity
from ..summary import (
    SummaryGenerationRequest,
    SummaryGenerator,
    SummaryMessage,
    UnavailableSummaryGenerator,
)
from ..telemetry import MetricsRegistry


class ShortTermMemoryService:
    def __init__(
        self,
        store: SessionStore,
        *,
        config_provider: ShortTermMemoryConfigProvider,
        summary_generator: SummaryGenerator | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._store = store
        self._config_provider = config_provider
        self._summary_generator = summary_generator or UnavailableSummaryGenerator()
        self._metrics = metrics or MetricsRegistry()

    def _config(self, identity: InvocationIdentity):
        try:
            config = self._config_provider.get(identity)
            config_version_id = identity.config_version_for("SHORT_TERM_MEMORY")
            if config_version_id is not None:
                self._metrics.set(
                    "component_config_active_version",
                    config_version_id,
                    {"component": "SHORT_TERM_MEMORY"},
                )
            return config
        except RuntimeConfigUnavailable as error:
            raise RuntimeConfigProblem(identity.request_id) from error

    @staticmethod
    def _scope(identity: InvocationIdentity) -> ScopeKey:
        if identity.session_id is None:
            raise ValueError("Actor Token must contain a sessionId")
        return (
            identity.tenant_id,
            identity.user_id,
            identity.agent_id,
            identity.session_id,
        )

    async def commit_turn(
        self,
        identity: InvocationIdentity,
        turn: ConversationTurn,
        idempotency_key: str,
    ) -> StoreCommitResult:
        config = self._config(identity)
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "turnId": turn.turn_id,
                    "userMessage": turn.user_message,
                    "assistantMessage": turn.assistant_message,
                    "occurredAt": turn.occurred_at.isoformat(),
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        safe_turn = replace(
            turn,
            user_message=redact_sensitive_content(turn.user_message),
            assistant_message=redact_sensitive_content(turn.assistant_message),
        )
        try:
            result = await self._store.commit(
                self._scope(identity),
                safe_turn,
                idempotency_key,
                fingerprint,
                max_messages=config.max_turns * 2,
                ttl_seconds=config.ttl_seconds,
            )
            self._metrics.increment(
                "short_term_commit_total",
                {"result": "duplicate" if result.duplicate else "success"},
            )
            return result
        except IdempotencyConflictError as error:
            self._metrics.increment("short_term_commit_total", {"result": "conflict"})
            raise IdempotencyProblem(identity.request_id) from error
        except StoreUnavailableError as error:
            self._metrics.increment("short_term_commit_total", {"result": "unavailable"})
            raise DependencyProblem(identity.request_id) from error

    async def prepare_context(
        self,
        identity: InvocationIdentity,
        *,
        max_context_tokens: int,
    ) -> PreparedContext:
        config = self._config(identity)
        effective_max_context_tokens = min(
            max_context_tokens, config.max_context_tokens
        )
        try:
            scope = self._scope(identity)
            messages = await self._store.read(scope)
            summary = await self._store.read_summary(scope)
        except StoreUnavailableError as error:
            raise DependencyProblem(identity.request_id) from error
        visible_messages = _messages_after_summary(messages, summary)
        summary_for_context = summary
        summary_status = "AVAILABLE" if summary else "NOT_AVAILABLE"
        used_tokens = 0
        if summary is not None:
            summary_tokens = _estimate_tokens(summary.summary)
            if summary_tokens <= effective_max_context_tokens:
                used_tokens = summary_tokens
            else:
                summary_for_context = None
                summary_status = "OMITTED_BUDGET"
        message_groups: list[list[StoredMessage]] = []
        for message in visible_messages:
            if not message_groups or message_groups[-1][0].turn_id != message.turn_id:
                message_groups.append([message])
            else:
                message_groups[-1].append(message)
        selected_groups: list[list[StoredMessage]] = []
        for group in reversed(message_groups):
            group_tokens = sum(_estimate_tokens(message.content) for message in group)
            if used_tokens + group_tokens > effective_max_context_tokens:
                break
            selected_groups.append(group)
            used_tokens += group_tokens
        selected = [
            message
            for group in reversed(selected_groups)
            for message in group
        ]
        self._metrics.increment(
            "short_term_context_hits_total" if selected or summary_for_context else "short_term_context_misses_total"
        )
        return PreparedContext(
            messages=selected,
            trimmed_message_count=len(visible_messages) - len(selected),
            estimated_token_count=used_tokens,
            summary=summary_for_context,
            summary_status=(
                summary_status
            ) if config.summary_enabled else "DISABLED",
        )

    async def refresh_summary_if_needed(self, identity: InvocationIdentity) -> str:
        config = self._config(identity)
        if not config.summary_enabled:
            return "DISABLED"
        scope = self._scope(identity)
        try:
            messages = await self._store.read(scope)
            current = await self._store.read_summary(scope)
            visible = _messages_after_summary(messages, current)
            groups = _turn_groups(visible)
            if len(groups) < config.summary_trigger_turns:
                return "NOT_DUE"
            keep_turns = max(1, config.summary_trigger_turns // 2)
            candidate_groups = groups[:-keep_turns]
            if not candidate_groups:
                return "NOT_DUE"
            candidates = tuple(
                SummaryMessage(message.turn_id, message.role, message.content)
                for group in candidate_groups
                for message in group
            )
            through_turn_id = candidate_groups[-1][-1].turn_id
            generated = await self._summary_generator.generate(
                SummaryGenerationRequest(
                    messages=candidates,
                    previous_summary=current.summary if current else None,
                    model_alias=config.summary_model_alias,
                    request_id=identity.request_id,
                    trace_parent=identity.trace_parent,
                )
            )
            safe_summary = redact_sensitive_content(generated.summary.strip())
            if not safe_summary or len(safe_summary) > 4000:
                raise ValueError("Generated summary is outside the accepted bounds")
            written = await self._store.write_summary(
                scope,
                ConversationSummary(
                    summary=safe_summary,
                    through_turn_id=through_turn_id,
                    model=generated.model,
                    updated_at=datetime.now(UTC),
                ),
                expected_through_turn_id=(current.through_turn_id if current else None),
                ttl_seconds=config.ttl_seconds,
            )
            result = "SUCCESS" if written else "STALE"
            self._metrics.increment(
                "short_term_summary_total", {"result": result.lower()}
            )
            return result
        except Exception:
            self._metrics.increment(
                "short_term_summary_total", {"result": "degraded"}
            )
            return "DEGRADED"

    async def clear_session(self, identity: InvocationIdentity) -> bool:
        try:
            return await self._store.clear(self._scope(identity))
        except StoreUnavailableError as error:
            raise DependencyProblem(identity.request_id) from error


def _estimate_tokens(content: str) -> int:
    return max(1, (len(content.encode("utf-8")) + 2) // 3)


def _turn_groups(messages: list[StoredMessage]) -> list[list[StoredMessage]]:
    groups: list[list[StoredMessage]] = []
    for message in messages:
        if not groups or groups[-1][0].turn_id != message.turn_id:
            groups.append([message])
        else:
            groups[-1].append(message)
    return groups


def _messages_after_summary(
    messages: list[StoredMessage], summary: ConversationSummary | None
) -> list[StoredMessage]:
    if summary is None:
        return messages
    last_covered_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if messages[index].turn_id == summary.through_turn_id
        ),
        None,
    )
    if last_covered_index is None:
        return messages
    return messages[last_covered_index + 1 :]
