CREATE TABLE IF NOT EXISTS planning_skill_versions (
    skill_id varchar(80) NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    tenant_id varchar(128) NOT NULL,
    agent_id varchar(128) NOT NULL,
    skill_name varchar(64) NOT NULL,
    complexity varchar(16) NOT NULL CHECK (complexity IN ('SIMPLE', 'COMPLEX')),
    status varchar(16) NOT NULL CHECK (status IN ('DRAFT')),
    skill_markdown text NOT NULL,
    decision_summary text NOT NULL,
    validation_json jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (skill_id, version)
);

CREATE INDEX IF NOT EXISTS idx_planning_skill_versions_scope
    ON planning_skill_versions (tenant_id, agent_id, skill_id, version DESC);

CREATE TABLE IF NOT EXISTS planning_skill_idempotency (
    tenant_id varchar(128) NOT NULL,
    agent_id varchar(128) NOT NULL,
    idempotency_key varchar(128) NOT NULL,
    request_fingerprint char(64) NOT NULL,
    operation_type varchar(16) NOT NULL CHECK (operation_type IN ('GENERATE', 'REVISE')),
    skill_id varchar(80) NOT NULL,
    skill_version integer NOT NULL CHECK (skill_version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, agent_id, idempotency_key)
);

-- 逻辑关系：planning_skill_idempotency(skill_id, skill_version)
-- -> planning_skill_versions(skill_id, version)。按项目约束不创建物理外键。
