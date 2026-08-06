CREATE TABLE IF NOT EXISTS planning_execution_plans (
    tenant_id varchar(128) NOT NULL,
    agent_id varchar(128) NOT NULL,
    user_id varchar(128) NOT NULL,
    plan_id varchar(80) NOT NULL,
    task_id varchar(256) NOT NULL,
    status varchar(32) NOT NULL
        CHECK (status IN ('ACTIVE', 'REPLAN_REQUIRED', 'COMPLETED', 'CANCELLED')),
    revision integer NOT NULL CHECK (revision > 0),
    plan_json jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, agent_id, user_id, plan_id)
);

CREATE INDEX IF NOT EXISTS idx_planning_execution_plans_task
    ON planning_execution_plans
       (tenant_id, agent_id, user_id, task_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS planning_plan_idempotency (
    tenant_id varchar(128) NOT NULL,
    agent_id varchar(128) NOT NULL,
    user_id varchar(128) NOT NULL,
    operation varchar(256) NOT NULL,
    idempotency_key varchar(128) NOT NULL,
    request_fingerprint char(64) NOT NULL,
    response_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, agent_id, user_id, operation, idempotency_key)
);

-- 计划聚合与幂等响应通过身份范围、operation和plan_id保持逻辑关系；
-- 按项目数据库约束不创建物理外键。
