from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.ai.errors import AIRunNotFoundError
from figure_data.ai.types import AIRunRecord, NewAIRun, PromptDefinition
from figure_data.db.enums import AIPromptStatus, AIRunStatus

RAW_OUTPUT_EXCERPT_LIMIT = 1000


class AIRunRepository(Protocol):
    def ensure_prompt_version(self, session: Session, prompt: PromptDefinition) -> UUID:
        """Return a database prompt version id, creating it when needed."""

    def create_run(self, session: Session, run: NewAIRun) -> UUID:
        """Create a running AI run."""

    def mark_succeeded(
        self,
        session: Session,
        *,
        run_id: UUID,
        output_snapshot: dict[str, Any],
        raw_output: str,
    ) -> None:
        """Mark an AI run as succeeded."""

    def mark_failed(
        self,
        session: Session,
        *,
        run_id: UUID,
        error_code: str,
        error_message: str,
        raw_output: str | None,
    ) -> None:
        """Mark an AI run as failed."""


class PostgresAIRunRepository:
    def ensure_prompt_version(self, session: Session, prompt: PromptDefinition) -> UUID:
        return ensure_prompt_version(session, prompt)

    def create_run(self, session: Session, run: NewAIRun) -> UUID:
        return create_ai_run(session, run)

    def mark_succeeded(
        self,
        session: Session,
        *,
        run_id: UUID,
        output_snapshot: dict[str, Any],
        raw_output: str,
    ) -> None:
        mark_ai_run_succeeded(
            session,
            run_id=run_id,
            output_snapshot=output_snapshot,
            raw_output=raw_output,
        )

    def mark_failed(
        self,
        session: Session,
        *,
        run_id: UUID,
        error_code: str,
        error_message: str,
        raw_output: str | None,
    ) -> None:
        mark_ai_run_failed(
            session,
            run_id=run_id,
            error_code=error_code,
            error_message=error_message,
            raw_output=raw_output,
        )


def ensure_prompt_version(session: Session, prompt: PromptDefinition) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_prompt_versions (
              id, prompt_key, prompt_version, purpose, system_prompt,
              user_prompt_template, output_schema_name, output_schema_version,
              status, created_at
            ) values (
              gen_random_uuid(), :prompt_key, :prompt_version, :purpose, :system_prompt,
              :user_prompt_template, :output_schema_name, :output_schema_version,
              :status, :created_at
            )
            on conflict on constraint uq_ai_prompt_versions_key_version do update
            set purpose = excluded.purpose
            returning id
            """
        ),
        {
            "prompt_key": prompt.prompt_key,
            "prompt_version": prompt.prompt_version,
            "purpose": prompt.purpose,
            "system_prompt": prompt.system_prompt,
            "user_prompt_template": prompt.user_prompt_template,
            "output_schema_name": prompt.output_schema_name,
            "output_schema_version": prompt.output_schema_version,
            "status": AIPromptStatus.ACTIVE.value,
            "created_at": datetime.now(UTC),
        },
    ).scalar_one()
    return value if isinstance(value, UUID) else UUID(str(value))


def create_ai_run(session: Session, run: NewAIRun) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_runs (
              id, purpose, provider, model_name, prompt_version_id,
              input_hash, input_snapshot, output_snapshot, raw_output_excerpt,
              status, schema_valid, error_code, error_message,
              started_at, finished_at, created_by
            ) values (
              gen_random_uuid(), :purpose, :provider, :model_name, :prompt_version_id,
              :input_hash, cast(:input_snapshot as jsonb), null, null,
              :status, :schema_valid, null, null,
              :started_at, null, :created_by
            )
            returning id
            """
        ),
        {
            "purpose": run.purpose,
            "provider": run.provider,
            "model_name": run.model_name,
            "prompt_version_id": run.prompt_version_id,
            "input_hash": run.input_hash,
            "input_snapshot": json.dumps(run.input_snapshot, ensure_ascii=False),
            "status": AIRunStatus.RUNNING.value,
            "schema_valid": False,
            "started_at": datetime.now(UTC),
            "created_by": run.created_by,
        },
    ).scalar_one()
    return value if isinstance(value, UUID) else UUID(str(value))


def mark_ai_run_succeeded(
    session: Session,
    *,
    run_id: UUID,
    output_snapshot: dict[str, Any],
    raw_output: str,
) -> None:
    session.execute(
        text(
            """
            update figure_data.ai_runs
            set output_snapshot = cast(:output_snapshot as jsonb),
                raw_output_excerpt = :raw_output_excerpt,
                status = :status,
                schema_valid = :schema_valid,
                error_code = null,
                error_message = null,
                finished_at = :finished_at
            where id = :run_id
            """
        ),
        {
            "run_id": run_id,
            "output_snapshot": json.dumps(output_snapshot, ensure_ascii=False),
            "raw_output_excerpt": _excerpt(raw_output),
            "status": AIRunStatus.SUCCEEDED.value,
            "schema_valid": True,
            "finished_at": datetime.now(UTC),
        },
    )


def mark_ai_run_failed(
    session: Session,
    *,
    run_id: UUID,
    error_code: str,
    error_message: str,
    raw_output: str | None,
) -> None:
    session.execute(
        text(
            """
            update figure_data.ai_runs
            set raw_output_excerpt = :raw_output_excerpt,
                status = :status,
                schema_valid = :schema_valid,
                error_code = :error_code,
                error_message = :error_message,
                finished_at = :finished_at
            where id = :run_id
            """
        ),
        {
            "run_id": run_id,
            "raw_output_excerpt": _excerpt(raw_output),
            "status": AIRunStatus.FAILED.value,
            "schema_valid": False,
            "error_code": error_code,
            "error_message": error_message,
            "finished_at": datetime.now(UTC),
        },
    )


def get_ai_run(session: Session, run_id: UUID) -> AIRunRecord:
    row = (
        session.execute(
            text(
                """
                select
                  r.id as run_id,
                  r.purpose,
                  r.provider,
                  r.model_name,
                  r.prompt_version_id,
                  p.prompt_key,
                  p.prompt_version,
                  r.input_hash,
                  r.input_snapshot,
                  r.output_snapshot,
                  r.raw_output_excerpt,
                  r.status,
                  r.schema_valid,
                  r.error_code,
                  r.error_message,
                  r.started_at,
                  r.finished_at,
                  r.created_by
                from figure_data.ai_runs r
                left join figure_data.ai_prompt_versions p on p.id = r.prompt_version_id
                where r.id = :run_id
                """
            ),
            {"run_id": run_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AIRunNotFoundError(f"AI run not found: {run_id}")
    return _run_from_row(cast(Mapping[str, Any], row))


def _run_from_row(row: Mapping[str, Any]) -> AIRunRecord:
    return AIRunRecord(
        run_id=_uuid(row["run_id"]),
        purpose=str(row["purpose"]),
        provider=str(row["provider"]),
        model_name=str(row["model_name"]),
        prompt_version_id=_uuid(row["prompt_version_id"]),
        prompt_key=row["prompt_key"],
        prompt_version=row["prompt_version"],
        input_hash=str(row["input_hash"]),
        input_snapshot=dict(row["input_snapshot"]),
        output_snapshot=(
            dict(row["output_snapshot"]) if row["output_snapshot"] is not None else None
        ),
        raw_output_excerpt=row["raw_output_excerpt"],
        status=str(row["status"]),
        schema_valid=bool(row["schema_valid"]),
        error_code=row["error_code"],
        error_message=row["error_message"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created_by=str(row["created_by"]),
    )


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _excerpt(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:RAW_OUTPUT_EXCERPT_LIMIT]
