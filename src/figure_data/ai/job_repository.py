from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.db.enums import AIJobStatus


class AIGenerationJobTransitionError(ValueError):
    """Raised when an AI generation job cannot enter the requested state."""


@dataclass(frozen=True)
class NewAIGenerationJob:
    job_type: str
    target_type: str
    target_kind: str
    target_id: int
    created_by: str
    params: dict[str, Any]


@dataclass(frozen=True)
class AIGenerationJobRecord:
    id: UUID
    job_type: str
    target_type: str
    target_kind: str
    target_id: int
    status: str
    created_by: str
    params: dict[str, Any]
    result_ref_type: str | None
    result_ref_id: UUID | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


def create_job(session: Session, job: NewAIGenerationJob) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_generation_jobs (
              id, job_type, target_type, target_kind, target_id,
              status, created_by, params, result_ref_type, result_ref_id,
              error_code, error_message, started_at, finished_at,
              created_at, updated_at
            ) values (
              gen_random_uuid(), :job_type, :target_type, :target_kind, :target_id,
              :status, :created_by, cast(:params as jsonb), null, null,
              null, null, null, null, :now, :now
            )
            returning id
            """
        ),
        {
            "job_type": job.job_type,
            "target_type": job.target_type,
            "target_kind": job.target_kind,
            "target_id": job.target_id,
            "status": AIJobStatus.QUEUED.value,
            "created_by": job.created_by,
            "params": json.dumps(job.params, ensure_ascii=False),
            "now": datetime.now(UTC),
        },
    ).scalar_one()
    return _uuid(value)


def get_job(session: Session, job_id: UUID) -> AIGenerationJobRecord | None:
    row = (
        session.execute(
            text(
                f"""
                select {_select_columns()}
                from figure_data.ai_generation_jobs
                where id = :job_id
                """
            ),
            {"job_id": job_id},
        )
        .mappings()
        .one_or_none()
    )
    return _record_from_row(cast(Mapping[str, Any], row)) if row is not None else None


def list_jobs_for_target(
    session: Session,
    *,
    target_type: str,
    target_kind: str,
    target_id: int,
    limit: int,
) -> list[AIGenerationJobRecord]:
    rows = (
        session.execute(
            text(
                f"""
                select {_select_columns()}
                from figure_data.ai_generation_jobs
                where target_type = :target_type
                  and target_kind = :target_kind
                  and target_id = :target_id
                order by created_at desc, id
                limit :limit
                """
            ),
            {
                "target_type": target_type,
                "target_kind": target_kind,
                "target_id": target_id,
                "limit": limit,
            },
        )
        .mappings()
        .all()
    )
    return [_record_from_row(cast(Mapping[str, Any], row)) for row in rows]


def claim_queued_jobs(
    session: Session,
    *,
    limit: int,
    job_type: str | None = None,
) -> list[AIGenerationJobRecord]:
    rows = (
        session.execute(
            text(
                f"""
                with claimed as (
                  select id
                  from figure_data.ai_generation_jobs
                  where status = :queued_status
                    and (:job_type is null or job_type = :job_type)
                  order by created_at, id
                  limit :limit
                  for update skip locked
                )
                update figure_data.ai_generation_jobs jobs
                set status = :running_status,
                    started_at = :now,
                    updated_at = :now
                from claimed
                where jobs.id = claimed.id
                returning {_returning_columns("jobs")}
                """
            ),
            {
                "queued_status": AIJobStatus.QUEUED.value,
                "running_status": AIJobStatus.RUNNING.value,
                "job_type": job_type,
                "limit": limit,
                "now": datetime.now(UTC),
            },
        )
        .mappings()
        .all()
    )
    return [_record_from_row(cast(Mapping[str, Any], row)) for row in rows]


def mark_running(session: Session, job_id: UUID) -> AIGenerationJobRecord:
    return _transition(
        session,
        job_id=job_id,
        expected_status=AIJobStatus.QUEUED.value,
        new_status=AIJobStatus.RUNNING.value,
        assignments="started_at = :now, updated_at = :now",
        extra_params={},
    )


def mark_succeeded(
    session: Session,
    job_id: UUID,
    *,
    result_ref_type: str,
    result_ref_id: UUID,
) -> AIGenerationJobRecord:
    return _transition(
        session,
        job_id=job_id,
        expected_status=AIJobStatus.RUNNING.value,
        new_status=AIJobStatus.SUCCEEDED.value,
        assignments=(
            "result_ref_type = :result_ref_type, result_ref_id = :result_ref_id, "
            "error_code = null, error_message = null, finished_at = :now, updated_at = :now"
        ),
        extra_params={"result_ref_type": result_ref_type, "result_ref_id": result_ref_id},
    )


def mark_failed(
    session: Session,
    job_id: UUID,
    *,
    error_code: str,
    error_message: str,
) -> AIGenerationJobRecord:
    return _transition(
        session,
        job_id=job_id,
        expected_status=AIJobStatus.RUNNING.value,
        new_status=AIJobStatus.FAILED.value,
        assignments=(
            "error_code = :error_code, error_message = :error_message, "
            "finished_at = :now, updated_at = :now"
        ),
        extra_params={"error_code": error_code, "error_message": error_message},
    )


def _transition(
    session: Session,
    *,
    job_id: UUID,
    expected_status: str,
    new_status: str,
    assignments: str,
    extra_params: dict[str, Any],
) -> AIGenerationJobRecord:
    params = {
        "job_id": job_id,
        "expected_status": expected_status,
        "status": new_status,
        "now": datetime.now(UTC),
        **extra_params,
    }
    row = (
        session.execute(
            text(
                f"""
                update figure_data.ai_generation_jobs
                set status = :status,
                    {assignments}
                where id = :job_id
                  and status = :expected_status
                returning {_select_columns()}
                """
            ),
            params,
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AIGenerationJobTransitionError(
            f"AI generation job {job_id} cannot transition from {expected_status} to {new_status}"
        )
    return _record_from_row(cast(Mapping[str, Any], row))


def _select_columns() -> str:
    return (
        "id, job_type, target_type, target_kind, target_id, status, created_by, params, "
        "result_ref_type, result_ref_id, error_code, error_message, started_at, finished_at, "
        "created_at, updated_at"
    )


def _returning_columns(prefix: str) -> str:
    return ", ".join(f"{prefix}.{column}" for column in _select_columns().split(", "))


def _record_from_row(row: Mapping[str, Any]) -> AIGenerationJobRecord:
    return AIGenerationJobRecord(
        id=_uuid(row["id"]),
        job_type=str(row["job_type"]),
        target_type=str(row["target_type"]),
        target_kind=str(row["target_kind"]),
        target_id=int(row["target_id"]),
        status=str(row["status"]),
        created_by=str(row["created_by"]),
        params=_json_object(row["params"]),
        result_ref_type=row["result_ref_type"],
        result_ref_id=_optional_uuid(row["result_ref_id"]),
        error_code=row["error_code"],
        error_message=row["error_message"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        loaded = json.loads(value)
        return dict(loaded) if isinstance(loaded, dict) else {}
    return {}


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _optional_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    return _uuid(value)
