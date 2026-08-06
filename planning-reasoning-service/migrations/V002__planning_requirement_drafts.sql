CREATE TABLE IF NOT EXISTS planning_requirement_drafts (
    tenant_id varchar(128) NOT NULL,
    agent_id varchar(128) NOT NULL,
    user_id varchar(128) NOT NULL,
    task_id varchar(256) NOT NULL,
    last_session_id varchar(256) NOT NULL,
    draft_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, agent_id, user_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_planning_requirement_drafts_updated
    ON planning_requirement_drafts (tenant_id, agent_id, user_id, updated_at DESC);

-- 逻辑关系由tenant_id、agent_id、user_id和task_id表达；按项目约束不创建物理外键。
