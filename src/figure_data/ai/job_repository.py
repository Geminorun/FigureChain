from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
    queue_backend: str
    queue_name: str | None
    queue_job_id: str | None
    enqueued_at: datetime | None
    attempt_count: int
    max_attempts: int
    next_run_at: datetime | None
    cancel_requested_at: datetime | None
    worker_id: str | None
    heartbeat_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AIJobEventRecord:
    id: UUID
    job_id: UUID
    event_type: str
    actor: str
    message: str | None
    metadata: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class AIJobQueueHealthRecord:
    status_counts: dict[str, int]
    queued_count: int
    running_count: int
    succeeded_count: int
    failed_count: int
    cancelled_count: int
    stale_running_count: int
    oldest_queued_at: datetime | None


def create_job(session: Session, job: NewAIGenerationJob) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_generation_jobs (
              id, job_type, target_type, target_kind, target_id,
              status, created_by, params, result_ref_type, result_ref_id,
              error_code, error_message, started_at, finished_at,
              queue_backend, queue_name, queue_job_id, enqueued_at,
              attempt_count, max_attempts, next_run_at, cancel_requested_at,
              worker_id, heartbeat_at,
              created_at, updated_at
            ) values (
              gen_random_uuid(), :job_type, :target_type, :target_kind, :target_id,
              :status, :created_by, cast(:params as jsonb), null, null,
              null, null, null, null,
              :queue_backend, null, null, null,
              :attempt_count, :max_attempts, null, null,
              null, null,
              :now, :now
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
            "queue_backend": "database",
            "attempt_count": 0,
            "max_attempts": 3,
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


def list_requeueable_jobs(
    session: Session,
    *,
    limit: int,
) -> list[AIGenerationJobRecord]:
    rows = (
        session.execute(
            text(
                f"""
                select {_select_columns()}
                from figure_data.ai_generation_jobs
                where status = :queued_status
                  and (next_run_at is null or next_run_at <= :now)
                order by created_at, id
                limit :limit
                """
            ),
            {
                "queued_status": AIJobStatus.QUEUED.value,
                "now": datetime.now(UTC),
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


def claim_queued_job_by_id(
    session: Session,
    job_id: UUID,
    *,
    worker_id: str,
) -> AIGenerationJobRecord | None:
    row = (
        session.execute(
            text(
                f"""
                update figure_data.ai_generation_jobs
                set status = :running_status,
                    started_at = coalesce(started_at, :now),
                    worker_id = :worker_id,
                    heartbeat_at = :now,
                    attempt_count = attempt_count + 1,
                    updated_at = :now
                where id = :job_id
                  and status = :queued_status
                  and (next_run_at is null or next_run_at <= :now)
                  and cancel_requested_at is null
                returning {_select_columns()}
                """
            ),
            {
                "job_id": job_id,
                "queued_status": AIJobStatus.QUEUED.value,
                "running_status": AIJobStatus.RUNNING.value,
                "worker_id": worker_id,
                "now": datetime.now(UTC),
            },
        )
        .mappings()
        .one_or_none()
    )
    return _record_from_row(cast(Mapping[str, Any], row)) if row is not None else None


def touch_job_heartbeat(
    session: Session,
    job_id: UUID,
    *,
    worker_id: str,
) -> None:
    session.execute(
        text(
            """
            update figure_data.ai_generation_jobs
            set worker_id = :worker_id,
                heartbeat_at = :now,
                updated_at = :now
            where id = :job_id
              and status = :running_status
            """
        ),
        {
            "job_id": job_id,
            "worker_id": worker_id,
            "running_status": AIJobStatus.RUNNING.value,
            "now": datetime.now(UTC),
        },
    )


def cancel_queued_job(
    session: Session,
    job_id: UUID,
    *,
    cancelled_by: str,
) -> AIGenerationJobRecord:
    return _transition(
        session,
        job_id=job_id,
        expected_status=AIJobStatus.QUEUED.value,
        new_status=AIJobStatus.CANCELLED.value,
        assignments="cancel_requested_at = :now, finished_at = :now, updated_at = :now",
        extra_params={"cancelled_by": cancelled_by},
    )


def request_running_job_cancel(
    session: Session,
    job_id: UUID,
    *,
    cancelled_by: str,
) -> AIGenerationJobRecord:
    return _transition(
        session,
        job_id=job_id,
        expected_status=AIJobStatus.RUNNING.value,
        new_status=AIJobStatus.RUNNING.value,
        assignments="cancel_requested_at = :now, updated_at = :now",
        extra_params={"cancelled_by": cancelled_by},
    )


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


def schedule_job_retry(
    session: Session,
    job_id: UUID,
    *,
    error_code: str,
    error_message: str,
    delay_seconds: int,
) -> AIGenerationJobRecord:
    next_run_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
    return _transition(
        session,
        job_id=job_id,
        expected_status=AIJobStatus.RUNNING.value,
        new_status=AIJobStatus.QUEUED.value,
        assignments=(
            "error_code = :error_code, error_message = :error_message, "
            "next_run_at = :next_run_at, worker_id = null, heartbeat_at = null, updated_at = :now"
        ),
        extra_params={
            "error_code": error_code,
            "error_message": error_message,
            "next_run_at": next_run_at,
        },
    )


def record_job_event(
    session: Session,
    *,
    job_id: UUID,
    event_type: str,
    actor: str,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_job_events (
              id, job_id, event_type, actor, message, metadata_json, created_at
            ) values (
              gen_random_uuid(), :job_id, :event_type, :actor, :message,
              cast(:metadata_json as jsonb), :created_at
            )
            returning id
            """
        ),
        {
            "job_id": job_id,
            "event_type": event_type,
            "actor": actor,
            "message": message,
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
            "created_at": datetime.now(UTC),
        },
    ).scalar_one()
    return _uuid(value)


def list_job_events(session: Session, job_id: UUID) -> list[AIJobEventRecord]:
    rows = (
        session.execute(
            text(
                """
                select id, job_id, event_type, actor, message, metadata_json, created_at
                from figure_data.ai_job_events
                where job_id = :job_id
                order by created_at, id
                """
            ),
            {"job_id": job_id},
        )
        .mappings()
        .all()
    )
    return [_event_from_row(cast(Mapping[str, Any], row)) for row in rows]


def get_job_queue_health(
    session: Session,
    *,
    stale_after_seconds: int,
) -> AIJobQueueHealthRecord:
    stale_cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    row = (
        session.execute(
            text(
                """
                select
                  count(*) filter (where status = 'queued') as queued_count,
                  count(*) filter (where status = 'running') as running_count,
                  count(*) filter (where status = 'succeeded') as succeeded_count,
                  count(*) filter (where status = 'failed') as failed_count,
                  count(*) filter (where status = 'cancelled') as cancelled_count,
                  count(*) filter (
                    where status = 'running'
                      and (heartbeat_at is null or heartbeat_at < :stale_cutoff)
                  ) as stale_running_count,
                  min(created_at) filter (where status = 'queued') as oldest_queued_at
                from figure_data.ai_generation_jobs
                """
            ),
            {"stale_cutoff": stale_cutoff},
        )
        .mappings()
        .one_or_none()
    )
    values = cast(Mapping[str, Any], row) if row is not None else {}
    queued_count = int(values.get("queued_count") or 0)
    running_count = int(values.get("running_count") or 0)
    succeeded_count = int(values.get("succeeded_count") or 0)
    failed_count = int(values.get("failed_count") or 0)
    cancelled_count = int(values.get("cancelled_count") or 0)
    return AIJobQueueHealthRecord(
        status_counts={
            AIJobStatus.QUEUED.value: queued_count,
            AIJobStatus.RUNNING.value: running_count,
            AIJobStatus.SUCCEEDED.value: succeeded_count,
            AIJobStatus.FAILED.value: failed_count,
            AIJobStatus.CANCELLED.value: cancelled_count,
        },
        queued_count=queued_count,
        running_count=running_count,
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        cancelled_count=cancelled_count,
        stale_running_count=int(values.get("stale_running_count") or 0),
        oldest_queued_at=values.get("oldest_queued_at"),
    )


def mark_enqueued(
    session: Session,
    job_id: UUID,
    *,
    queue_backend: str,
    queue_name: str,
    queue_job_id: str,
) -> AIGenerationJobRecord:
    return _transition_any_status(
        session,
        job_id=job_id,
        assignments=(
            "queue_backend = :queue_backend, queue_name = :queue_name, "
            "queue_job_id = :queue_job_id, enqueued_at = :now, updated_at = :now"
        ),
        extra_params={
            "queue_backend": queue_backend,
            "queue_name": queue_name,
            "queue_job_id": queue_job_id,
        },
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


def _transition_any_status(
    session: Session,
    *,
    job_id: UUID,
    assignments: str,
    extra_params: dict[str, Any],
) -> AIGenerationJobRecord:
    params = {
        "job_id": job_id,
        "now": datetime.now(UTC),
        **extra_params,
    }
    row = (
        session.execute(
            text(
                f"""
                update figure_data.ai_generation_jobs
                set {assignments}
                where id = :job_id
                returning {_select_columns()}
                """
            ),
            params,
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AIGenerationJobTransitionError(f"AI generation job {job_id} was not found")
    return _record_from_row(cast(Mapping[str, Any], row))


def _select_columns() -> str:
    return (
        "id, job_type, target_type, target_kind, target_id, status, created_by, params, "
        "result_ref_type, result_ref_id, error_code, error_message, started_at, finished_at, "
        "queue_backend, queue_name, queue_job_id, enqueued_at, attempt_count, max_attempts, "
        "next_run_at, cancel_requested_at, worker_id, heartbeat_at, "
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
        queue_backend=str(row["queue_backend"]),
        queue_name=row["queue_name"],
        queue_job_id=row["queue_job_id"],
        enqueued_at=row["enqueued_at"],
        attempt_count=int(row["attempt_count"]),
        max_attempts=int(row["max_attempts"]),
        next_run_at=row["next_run_at"],
        cancel_requested_at=row["cancel_requested_at"],
        worker_id=row["worker_id"],
        heartbeat_at=row["heartbeat_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _event_from_row(row: Mapping[str, Any]) -> AIJobEventRecord:
    return AIJobEventRecord(
        id=_uuid(row["id"]),
        job_id=_uuid(row["job_id"]),
        event_type=str(row["event_type"]),
        actor=str(row["actor"]),
        message=row["message"],
        metadata=_json_object(row["metadata_json"]),
        created_at=row["created_at"],
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
