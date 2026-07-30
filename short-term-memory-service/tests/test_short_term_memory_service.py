from datetime import datetime, timedelta, timezone

from short_term_memory.models import CallerScope, WorkbenchUpdate
from short_term_memory.service import InMemoryTaskStore, ShortTermMemoryService


def test_expired_task_is_not_returned() -> None:
    now = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)
    service = ShortTermMemoryService(InMemoryTaskStore(), clock=lambda: now)
    scope = CallerScope(tenant_id="tenant", agent_id="agent", user_id="user")
    service.save_workbench(
        scope,
        "task-expiry",
        WorkbenchUpdate(status="ACTIVE", expiresInSeconds=60),
    )
    assert service.get_task(scope, "task-expiry") is not None

    now += timedelta(seconds=61)
    assert service.get_task(scope, "task-expiry") is None
