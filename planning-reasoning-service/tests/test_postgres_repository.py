import os
from uuid import uuid4

import psycopg2
import pytest

from planning_reasoning.models import SkillGenerateRequest, SkillReviseRequest
from planning_reasoning.repository import PostgreSQLSkillRepository
from planning_reasoning.service import RequirementAnalyzer, SkillAuthoringService, SkillValidator


def test_postgres_repository_keeps_versions_idempotent_isolated_and_without_foreign_keys() -> None:
    dsn = os.getenv("PLANNING_REASONING_POSTGRES_DSN")
    if not dsn:
        pytest.skip("PLANNING_REASONING_POSTGRES_DSN is not configured")
    suffix = uuid4().hex[:12]
    tenant_id = f"planning-acceptance-tenant-{suffix}"
    agent_id = f"planning-acceptance-agent-{suffix}"
    repository = PostgreSQLSkillRepository(dsn)
    authoring = SkillAuthoringService(
        RequirementAnalyzer(), SkillValidator(), repository
    )
    request = SkillGenerateRequest.model_validate(
        {
            "name": "持久化Skill",
            "description": "验证规划Skill的持久化、幂等和版本隔离能力",
            "requirements": {
                "goal": "验证持久化",
                "expectedInputs": ["测试输入"],
                "expectedOutputs": ["测试输出"],
                "constraints": ["只写入本次验收数据"],
            },
        }
    )
    generated = authoring.generate(
        request,
        tenant_id=tenant_id,
        agent_id=agent_id,
        idempotency_key=f"generate-{suffix}",
    )
    replay = authoring.generate(
        request,
        tenant_id=tenant_id,
        agent_id=agent_id,
        idempotency_key=f"generate-{suffix}",
    )
    revised = authoring.revise(
        generated.skill_id,
        SkillReviseRequest.model_validate(
            {
                "baseVersion": 1,
                "failure": {
                    "failedStep": "持久化检查",
                    "errorCode": "TEST_FAILURE",
                    "summary": "模拟失败",
                },
                "adjustmentGoal": "生成第二版本",
            }
        ),
        tenant_id=tenant_id,
        agent_id=agent_id,
        idempotency_key=f"revise-{suffix}",
    )

    assert replay.skill_id == generated.skill_id
    assert revised.version == 2
    assert authoring.get(
        generated.skill_id, 1, tenant_id=tenant_id, agent_id=agent_id
    ) is not None
    assert authoring.get(
        generated.skill_id,
        1,
        tenant_id=tenant_id,
        agent_id=f"other-{suffix}",
    ) is None
    with psycopg2.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT count(*) FROM information_schema.table_constraints
            WHERE table_schema=current_schema()
              AND table_name=ANY(%s) AND constraint_type='FOREIGN KEY'
            """,
            (["planning_skill_versions", "planning_skill_idempotency"],),
        )
        assert cursor.fetchone()[0] == 0
