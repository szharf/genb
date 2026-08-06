CREATE SCHEMA IF NOT EXISTS long_term_memory_service;

CREATE TABLE IF NOT EXISTS long_term_memory_service.memory_extraction_jobs (
    id varchar(64) PRIMARY KEY,
    tenant_id varchar(128) NOT NULL,
    user_id varchar(128) NOT NULL,
    agent_id varchar(128) NOT NULL,
    conversation_id varchar(128) NOT NULL,
    turn_id varchar(128) NOT NULL,
    user_message text NOT NULL,
    assistant_message text NOT NULL,
    occurred_at timestamptz NOT NULL,
    idempotency_hash char(64) NOT NULL,
    request_fingerprint char(64) NOT NULL,
    status varchar(16) NOT NULL,
    attempt_count integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL,
    next_attempt_at timestamptz NOT NULL,
    lease_until timestamptz NULL,
    written_count integer NOT NULL DEFAULT 0,
    rejected_count integer NOT NULL DEFAULT 0,
    error_code varchar(64) NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT uk_ltm_service_extraction_idempotency UNIQUE (
        tenant_id, user_id, agent_id, idempotency_hash
    ),
    CONSTRAINT ck_ltm_service_extraction_status CHECK (
        status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'NO_WRITE', 'FAILED', 'DEAD')
    )
);

CREATE INDEX IF NOT EXISTS idx_ltm_service_extraction_claim
    ON long_term_memory_service.memory_extraction_jobs
    (status, next_attempt_at, lease_until, created_at);

CREATE TABLE IF NOT EXISTS long_term_memory_service.long_term_memories (
    id varchar(64) PRIMARY KEY,
    tenant_id varchar(128) NOT NULL,
    user_id varchar(128) NOT NULL,
    agent_id varchar(128) NOT NULL,
    memory_type varchar(32) NOT NULL,
    content text NOT NULL,
    content_hash char(64) NOT NULL,
    confidence numeric(5,4) NOT NULL,
    source_type varchar(32) NOT NULL,
    source_ref varchar(128) NOT NULL,
    status varchar(16) NOT NULL,
    last_confirmed_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    deleted_at timestamptz NULL,
    deleted_by varchar(128) NULL,
    delete_reason varchar(500) NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT ck_ltm_service_memory_type CHECK (
        memory_type IN ('USER_PREFERENCE', 'STABLE_FACT', 'USER_CONSTRAINT')
    ),
    CONSTRAINT ck_ltm_service_source_type CHECK (
        source_type IN ('CONVERSATION', 'KNOWLEDGE_BASE')
    ),
    CONSTRAINT ck_ltm_service_memory_status CHECK (
        status IN ('ACTIVE', 'SUPERSEDED', 'DELETED', 'EXPIRED')
    ),
    CONSTRAINT ck_ltm_service_confidence CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_ltm_service_exact_active
    ON long_term_memory_service.long_term_memories
    (tenant_id, user_id, agent_id, memory_type, content_hash)
    WHERE status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS idx_ltm_service_scope_active
    ON long_term_memory_service.long_term_memories
    (tenant_id, user_id, agent_id, status, expires_at);

CREATE TABLE IF NOT EXISTS long_term_memory_service.memory_audit_events (
    id bigserial PRIMARY KEY,
    tenant_id varchar(128) NOT NULL,
    user_id varchar(128) NOT NULL,
    agent_id varchar(128) NOT NULL,
    memory_id varchar(64) NOT NULL,
    actor varchar(128) NOT NULL,
    action varchar(32) NOT NULL,
    reason varchar(500) NULL,
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ltm_service_audit_scope
    ON long_term_memory_service.memory_audit_events
    (tenant_id, user_id, agent_id, created_at DESC);
