from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.ai.job_repository import (
    AIGenerationJobRecord,
    list_requeueable_jobs,
    mark_enqueued,
    record_job_event,
)
from figure_data.ai.queue import AIJobQueue
from figure_data.ai.redaction import redact_sensitive_text


@dataclass(frozen=True)
class RequeueAIJobsResult:
    scanned: int
    enqueued: int
    failed: int
    job_ids: list[UUID]


ListRequeueableJobsFn = Callable[[Session, int], list[AIGenerationJobRecord]]
MarkEnqueuedFn = Callable[..., object]
RecordEventFn = Callable[..., object]


def requeue_ai_jobs(
    *,
    session: Session,
    queue: AIJobQueue,
    actor: str,
    limit: int,
    queue_name: str,
    timeout_seconds: int,
    list_requeueable_jobs_fn: ListRequeueableJobsFn | None = None,
    mark_enqueued_fn: MarkEnqueuedFn = mark_enqueued,
    record_event_fn: RecordEventFn = record_job_event,
) -> RequeueAIJobsResult:
    """Enqueue recoverable AI jobs through the configured queue backend."""
    list_jobs = list_requeueable_jobs_fn or _list_requeueable_jobs
    jobs = list_jobs(session, limit)
    enqueued_job_ids: list[UUID] = []
    failed = 0

    for job in jobs:
        try:
            enqueued = queue.enqueue(
                job.id,
                queue_name=queue_name,
                timeout_seconds=timeout_seconds,
            )
            if enqueued.queue_job_id is None:
                failed += 1
                record_event_fn(
                    session,
                    job_id=job.id,
                    event_type="requeue_failed",
                    actor=actor,
                    message="AI job requeue failed",
                    metadata={"error": "queue backend did not return a queue job id"},
                )
                continue
            mark_enqueued_fn(
                session,
                job.id,
                queue_backend=enqueued.queue_backend,
                queue_name=enqueued.queue_name,
                queue_job_id=enqueued.queue_job_id,
            )
            record_event_fn(
                session,
                job_id=job.id,
                event_type="requeued",
                actor=actor,
                message="AI job requeued",
                metadata={
                    "queue_backend": enqueued.queue_backend,
                    "queue_name": enqueued.queue_name,
                    "queue_job_id": enqueued.queue_job_id,
                },
            )
            enqueued_job_ids.append(job.id)
        except Exception as exc:
            failed += 1
            record_event_fn(
                session,
                job_id=job.id,
                event_type="requeue_failed",
                actor=actor,
                message="AI job requeue failed",
                metadata={"error": redact_sensitive_text(str(exc))},
            )

    return RequeueAIJobsResult(
        scanned=len(jobs),
        enqueued=len(enqueued_job_ids),
        failed=failed,
        job_ids=enqueued_job_ids,
    )


def _list_requeueable_jobs(session: Session, limit: int) -> list[AIGenerationJobRecord]:
    return list_requeueable_jobs(session, limit=limit)
