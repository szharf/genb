import json
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Protocol

import psycopg2
from psycopg2.extras import RealDictCursor

from .models import RequirementDraft, SkillArtifact


class RequirementDraftRepository(Protocol):
    def get_draft(
        self, *, tenant_id: str, agent_id: str, user_id: str, task_id: str
    ) -> RequirementDraft | None: ...

    def save_draft(
        self,
        draft: RequirementDraft,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        task_id: str,
        session_id: str,
    ) -> None: ...


class InMemoryRequirementDraftRepository:
    def __init__(self) -> None:
        self._drafts: dict[tuple[str, str, str, str], RequirementDraft] = {}

    def get_draft(
        self, *, tenant_id: str, agent_id: str, user_id: str, task_id: str
    ) -> RequirementDraft | None:
        draft = self._drafts.get((tenant_id, agent_id, user_id, task_id))
        return draft.model_copy(deep=True) if draft is not None else None

    def save_draft(
        self,
        draft: RequirementDraft,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        task_id: str,
        session_id: str,
    ) -> None:
        del session_id
        self._drafts[(tenant_id, agent_id, user_id, task_id)] = draft.model_copy(deep=True)


class PostgreSQLRequirementDraftRepository:
    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN is required")
        self._dsn = dsn

    def get_draft(
        self, *, tenant_id: str, agent_id: str, user_id: str, task_id: str
    ) -> RequirementDraft | None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT draft_json FROM planning_requirement_drafts
                WHERE tenant_id=%s AND agent_id=%s AND user_id=%s AND task_id=%s
                """,
                (tenant_id, agent_id, user_id, task_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            payload = row[0]
            return RequirementDraft.model_validate_json(payload) if isinstance(payload, str) else RequirementDraft.model_validate(payload)

    def save_draft(
        self,
        draft: RequirementDraft,
        *,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        task_id: str,
        session_id: str,
    ) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO planning_requirement_drafts
                  (tenant_id, agent_id, user_id, task_id, last_session_id, draft_json, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,now())
                ON CONFLICT (tenant_id, agent_id, user_id, task_id)
                DO UPDATE SET last_session_id=EXCLUDED.last_session_id,
                              draft_json=EXCLUDED.draft_json,
                              updated_at=now()
                """,
                (
                    tenant_id,
                    agent_id,
                    user_id,
                    task_id,
                    session_id,
                    draft.model_dump_json(by_alias=True),
                ),
            )

    @contextmanager
    def _connection(self) -> Iterator:
        connection = psycopg2.connect(self._dsn, connect_timeout=3)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class SkillRepository(Protocol):
    def find_by_idempotency(
        self, tenant_id: str, agent_id: str, key: str, fingerprint: str
    ) -> SkillArtifact | None: ...

    def save_initial(
        self,
        artifact: SkillArtifact,
        tenant_id: str,
        agent_id: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> None: ...

    def get(
        self, skill_id: str, version: int, tenant_id: str, agent_id: str
    ) -> SkillArtifact | None: ...

    def save_revision(
        self,
        artifact: SkillArtifact,
        *,
        tenant_id: str,
        agent_id: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> SkillArtifact: ...

    def ready(self) -> bool: ...


class InMemorySkillRepository:
    def __init__(self) -> None:
        self._versions: dict[tuple[str, int], SkillArtifact] = {}
        self._idempotency: dict[tuple[str, str, str], tuple[str, str]] = {}
        self._revision_idempotency: dict[
            tuple[str, str, str], tuple[str, str, int]
        ] = {}
        self._owners: dict[str, tuple[str, str]] = {}

    def find_by_idempotency(
        self, tenant_id: str, agent_id: str, key: str, fingerprint: str
    ) -> SkillArtifact | None:
        existing = self._idempotency.get((tenant_id, agent_id, key))
        if existing is None:
            return None
        if existing[0] != fingerprint:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return self._versions[(existing[1], 1)]

    def save_initial(
        self,
        artifact: SkillArtifact,
        tenant_id: str,
        agent_id: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> None:
        self._versions[(artifact.skill_id, artifact.version)] = artifact
        self._owners[artifact.skill_id] = (tenant_id, agent_id)
        self._idempotency[(tenant_id, agent_id, idempotency_key)] = (
            fingerprint,
            artifact.skill_id,
        )

    def get(
        self, skill_id: str, version: int, tenant_id: str, agent_id: str
    ) -> SkillArtifact | None:
        if self._owners.get(skill_id) != (tenant_id, agent_id):
            return None
        return self._versions.get((skill_id, version))

    def save_revision(
        self,
        artifact: SkillArtifact,
        *,
        tenant_id: str,
        agent_id: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> SkillArtifact:
        identity_key = (tenant_id, agent_id, idempotency_key)
        existing = self._revision_idempotency.get(identity_key)
        if existing is not None:
            if existing[0] != fingerprint:
                raise ValueError("IDEMPOTENCY_CONFLICT")
            return self._versions[(existing[1], existing[2])]
        if self._owners.get(artifact.skill_id) != (tenant_id, agent_id):
            raise KeyError("SKILL_NOT_FOUND")
        latest = max(
            version
            for stored_id, version in self._versions
            if stored_id == artifact.skill_id
        )
        if artifact.version != latest + 1:
            raise ValueError("STALE_BASE_VERSION")
        self._versions[(artifact.skill_id, artifact.version)] = artifact
        self._revision_idempotency[identity_key] = (
            fingerprint,
            artifact.skill_id,
            artifact.version,
        )
        return artifact

    def ready(self) -> bool:
        return True


class PostgreSQLSkillRepository:
    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN is required")
        self._dsn = dsn

    def find_by_idempotency(
        self, tenant_id: str, agent_id: str, key: str, fingerprint: str
    ) -> SkillArtifact | None:
        with self._connection() as connection, connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT request_fingerprint, skill_id, skill_version
                FROM planning_skill_idempotency
                WHERE tenant_id=%s AND agent_id=%s AND idempotency_key=%s
                """,
                (tenant_id, agent_id, key),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            if row["request_fingerprint"] != fingerprint:
                raise ValueError("IDEMPOTENCY_CONFLICT")
            return self.get(row["skill_id"], row["skill_version"], tenant_id, agent_id)

    def save_initial(
        self,
        artifact: SkillArtifact,
        tenant_id: str,
        agent_id: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            self._insert_artifact(cursor, artifact, tenant_id, agent_id)
            cursor.execute(
                """
                INSERT INTO planning_skill_idempotency
                  (tenant_id, agent_id, idempotency_key, request_fingerprint,
                   operation_type, skill_id, skill_version)
                VALUES (%s,%s,%s,%s,'GENERATE',%s,%s)
                """,
                (
                    tenant_id,
                    agent_id,
                    idempotency_key,
                    fingerprint,
                    artifact.skill_id,
                    artifact.version,
                ),
            )

    def get(
        self, skill_id: str, version: int, tenant_id: str, agent_id: str
    ) -> SkillArtifact | None:
        with self._connection() as connection, connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT skill_id, version, skill_name, complexity, status,
                       skill_markdown, decision_summary, validation_json, created_at
                FROM planning_skill_versions
                WHERE skill_id=%s AND version=%s AND tenant_id=%s AND agent_id=%s
                """,
                (skill_id, version, tenant_id, agent_id),
            )
            row = cursor.fetchone()
            return _artifact_from_row(row) if row else None

    def save_revision(
        self,
        artifact: SkillArtifact,
        *,
        tenant_id: str,
        agent_id: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> SkillArtifact:
        existing = self._revision_by_idempotency(
            tenant_id, agent_id, idempotency_key, fingerprint
        )
        if existing is not None:
            return existing
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT version FROM planning_skill_versions
                WHERE skill_id=%s AND tenant_id=%s AND agent_id=%s
                ORDER BY version DESC LIMIT 1 FOR UPDATE
                """,
                (artifact.skill_id, tenant_id, agent_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError("SKILL_NOT_FOUND")
            if artifact.version != row[0] + 1:
                raise ValueError("STALE_BASE_VERSION")
            self._insert_artifact(cursor, artifact, tenant_id, agent_id)
            cursor.execute(
                """
                INSERT INTO planning_skill_idempotency
                  (tenant_id, agent_id, idempotency_key, request_fingerprint,
                   operation_type, skill_id, skill_version)
                VALUES (%s,%s,%s,%s,'REVISE',%s,%s)
                """,
                (
                    tenant_id,
                    agent_id,
                    idempotency_key,
                    fingerprint,
                    artifact.skill_id,
                    artifact.version,
                ),
            )
        return artifact

    def _revision_by_idempotency(
        self, tenant_id: str, agent_id: str, key: str, fingerprint: str
    ) -> SkillArtifact | None:
        with self._connection() as connection, connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT request_fingerprint, operation_type, skill_id, skill_version
                FROM planning_skill_idempotency
                WHERE tenant_id=%s AND agent_id=%s AND idempotency_key=%s
                """,
                (tenant_id, agent_id, key),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            if row["request_fingerprint"] != fingerprint or row["operation_type"] != "REVISE":
                raise ValueError("IDEMPOTENCY_CONFLICT")
            return self.get(row["skill_id"], row["skill_version"], tenant_id, agent_id)

    @staticmethod
    def _insert_artifact(cursor, artifact: SkillArtifact, tenant_id: str, agent_id: str) -> None:
        cursor.execute(
            """
            INSERT INTO planning_skill_versions
              (skill_id, version, tenant_id, agent_id, skill_name, complexity,
               status, skill_markdown, decision_summary, validation_json, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            """,
            (
                artifact.skill_id,
                artifact.version,
                tenant_id,
                agent_id,
                artifact.name,
                artifact.complexity,
                artifact.status,
                artifact.skill_markdown,
                artifact.decision_summary,
                artifact.validation.model_dump_json(),
                artifact.created_at,
            ),
        )

    def ready(self) -> bool:
        try:
            with self._connection() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
        except psycopg2.Error:
            return False

    def _connect(self):
        return psycopg2.connect(self._dsn, connect_timeout=3)

    @contextmanager
    def _connection(self) -> Iterator:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _artifact_from_row(row: dict[str, object]) -> SkillArtifact:
    validation = row["validation_json"]
    if isinstance(validation, str):
        validation = json.loads(validation)
    return SkillArtifact.model_validate(
        {
            "skillId": row["skill_id"],
            "version": row["version"],
            "name": row["skill_name"],
            "complexity": row["complexity"],
            "status": row["status"],
            "skillMarkdown": row["skill_markdown"],
            "decisionSummary": row["decision_summary"],
            "validation": validation,
            "createdAt": row["created_at"],
        }
    )
