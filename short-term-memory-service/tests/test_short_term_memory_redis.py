from datetime import datetime, timezone
import os
from uuid import uuid4

import pytest
from redis import Redis

from short_term_memory.models import CallerScope, WorkbenchUpdate
from short_term_memory.service import RedisTaskStore, ShortTermMemoryService


def test_redis_store_recovers_data_across_service_instances() -> None:
    password = os.getenv("SHORT_TERM_MEMORY_TEST_REDIS_PASSWORD")
    if password is None:
        pytest.skip("set SHORT_TERM_MEMORY_TEST_REDIS_PASSWORD to run the real Redis test")
    client = Redis(
        host=os.getenv("SHORT_TERM_MEMORY_TEST_REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("SHORT_TERM_MEMORY_TEST_REDIS_PORT", "6379")),
        db=int(os.getenv("SHORT_TERM_MEMORY_TEST_REDIS_DB", "15")),
        password=password,
        socket_connect_timeout=2,
    )
    prefix = f"genb:test:short-term-memory:{uuid4().hex}"
    scope = CallerScope(tenant_id="tenant-redis", agent_id="agent-redis", user_id="user-redis")
    first = ShortTermMemoryService(RedisTaskStore(client, prefix), clock=lambda: datetime.now(timezone.utc))
    second = ShortTermMemoryService(RedisTaskStore(client, prefix), clock=lambda: datetime.now(timezone.utc))
    try:
        first.save_workbench(scope, "task-redis", WorkbenchUpdate(status="PAUSED", progress="跨实例恢复", expiresInSeconds=300))
        restored = second.get_task(scope, "task-redis")
        assert restored is not None
        assert restored["workbench"]["progress"] == "跨实例恢复"
        assert second.delete_task(scope, "task-redis") is True
        assert first.get_task(scope, "task-redis") is None
    finally:
        for key in client.scan_iter(match=f"{prefix}:*"):
            client.delete(key)
