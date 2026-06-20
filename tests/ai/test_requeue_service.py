from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from figure_data.ai.job_repository import AIGenerationJobRecord
from figure_data.ai.queue import EnqueuedAIJob
from figure_data.ai.requeue import RequeueAIJobsResult, requeue_ai_jobs


@dataclass
class FakeQueue:
    enqueued: list[UUID] = field(default_factory=list)
    fail: bool = False

    def enqueue(
        self,
        job_id: UUID,
        *,
        queue_name: str,
        timeout_seconds: int,
        delay_seconds: int = 0,
        queue_job_id_suffix: str | None = None,
    ) -> EnqueuedAIJob:
        if self.fail:
            raise RuntimeError("failed with token=secret-value")
        self.enqueued.append(job_id)
        return EnqueuedAIJob(
            queue_backend="rq",
            queue_name=queue_name,
            queue_job_id=f"rq-{job_id}",
        )


def _job(job_id: UUID) -> AIGenerationJobRecord:
    now = datetime.now(UTC)
    return AIGenerationJobRecord(
        id=job_id,
        job_type="candidate_review_suggestion",
        target_type="candidate",
        target_kind="relationship",
        target_id=1,
        status="queued",
        created_by="local",
        params={},
        result_ref_type=None,
        result_ref_id=None,
        error_code=None,
        error_message=None,
        started_at=None,
        finished_at=None,
        queue_backend="database",
        queue_name=None,
        queue_job_id=None,
        enqueued_at=None,
        attempt_count=0,
        max_attempts=3,
        next_run_at=None,
        cancel_requested_at=None,
        worker_id=None,
        heartbeat_at=None,
        created_at=now,
        updated_at=now,
    )


def test_requeue_ai_jobs_enqueues_requeueable_jobs() -> None:
    job_id = uuid4()
    marked: list[UUID] = []
    events: list[tuple[UUID, str, dict[str, object]]] = []

    result = requeue_ai_jobs(
        session=object(),  # type: ignore[arg-type]
        queue=FakeQueue(),
        actor="local",
        limit=10,
        queue_name="figure-ai",
        timeout_seconds=300,
        list_requeueable_jobs_fn=lambda session, limit: [_job(job_id)],
        mark_enqueued_fn=(
            lambda session, job_id, queue_backend, queue_name, queue_job_id: marked.append(job_id)
        ),
        record_event_fn=(
            lambda session, job_id, event_type, actor, message, metadata: events.append(
                (job_id, event_type, metadata or {})
            )
        ),
    )

    assert result == RequeueAIJobsResult(scanned=1, enqueued=1, failed=0, job_ids=[job_id])
    assert marked == [job_id]
    assert events == [
        (
            job_id,
            "requeued",
            {
                "queue_backend": "rq",
                "queue_name": "figure-ai",
                "queue_job_id": f"rq-{job_id}",
            },
        )
    ]


def test_requeue_ai_jobs_records_redacted_enqueue_failure() -> None:
    job_id = uuid4()
    events: list[tuple[str, str | None, dict[str, object]]] = []

    result = requeue_ai_jobs(
        session=object(),  # type: ignore[arg-type]
        queue=FakeQueue(fail=True),
        actor="local",
        limit=10,
        queue_name="figure-ai",
        timeout_seconds=300,
        list_requeueable_jobs_fn=lambda session, limit: [_job(job_id)],
        record_event_fn=(
            lambda session, job_id, event_type, actor, message, metadata: events.append(
                (event_type, message, metadata or {})
            )
        ),
    )

    assert result == RequeueAIJobsResult(scanned=1, enqueued=0, failed=1, job_ids=[])
    assert events == [
            (
                "requeue_failed",
                "AI job requeue failed",
                {"error": "failed with token=[REDACTED]"},
            )
        ]
