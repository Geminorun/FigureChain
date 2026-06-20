from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError
from figure_chain.schemas import (
    AdminAIJobActionRequest,
    AdminAIJobsRequeueRequest,
    AiJobEventListResponse,
    AiJobEventResponse,
    AiJobHealthResponse,
    AiJobResponse,
)
from figure_chain.services.admin_ai_jobs import AdminAIJobsService
from figure_data.admin.operations import (
    AdminOperationCreate,
    AdminOperationRecord,
    AdminOperationUpdate,
)
from figure_data.ai.job_repository import AIGenerationJobRecord, AIJobListFilters
from figure_data.ai.queue import AIJobQueue
from figure_data.ai.requeue import RequeueAIJobsResult

NOW = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
JOB_ID = UUID("00000000-0000-0000-0000-000000000801")
OPERATION_ID = UUID("00000000-0000-0000-0000-000000000901")


class FakeAIJobsService:
    def __init__(self, *, fail_cancel: bool = False) -> None:
        self.fail_cancel = fail_cancel
        self.cancelled: list[tuple[UUID, str]] = []
        self.retried: list[tuple[UUID, str]] = []
        self.events = AiJobEventListResponse(
            items=[
                AiJobEventResponse(
                    id=uuid4(),
                    job_id=JOB_ID,
                    event_type="created",
                    actor="api",
                    message="AI job created",
                    metadata={},
                    created_at=NOW,
                )
            ],
            count=1,
        )
        self.health = AiJobHealthResponse(
            status_counts={"queued": 2, "running": 1},
            queued_count=2,
            running_count=1,
            succeeded_count=3,
            failed_count=4,
            cancelled_count=5,
            stale_running_count=1,
            oldest_queued_at=NOW,
        )

    def get_job(self, job_id: UUID) -> AiJobResponse:
        return _job_response(id=job_id)

    def list_job_events(self, job_id: UUID) -> AiJobEventListResponse:
        return self.events

    def cancel_job(self, job_id: UUID, *, cancelled_by: str) -> AiJobResponse:
        if self.fail_cancel:
            raise RuntimeError("cancel failed")
        self.cancelled.append((job_id, cancelled_by))
        return _job_response(id=job_id, status="cancelled")

    def retry_job(self, job_id: UUID, *, created_by: str) -> AiJobResponse:
        self.retried.append((job_id, created_by))
        return _job_response(id=uuid4(), status="queued")

    def get_queue_health(self) -> AiJobHealthResponse:
        return self.health


def test_admin_ai_jobs_service_lists_jobs_with_status_filter() -> None:
    seen_filters: list[AIJobListFilters] = []

    def list_jobs(session: Session, filters: AIJobListFilters) -> list[AIGenerationJobRecord]:
        seen_filters.append(filters)
        return [_job_record(JOB_ID)]

    service = AdminAIJobsService(
        cast(Session, object()),
        ai_jobs_service=FakeAIJobsService(),
        queue=cast(AIJobQueue, object()),
        list_jobs_fn=list_jobs,
    )

    response = service.list_jobs(status="queued", limit=25, offset=5)

    assert response.count == 1
    assert response.items[0].id == JOB_ID
    assert seen_filters == [
        AIJobListFilters(
            status="queued",
            target_kind=None,
            target_id=None,
            queue_backend=None,
            limit=25,
            offset=5,
        )
    ]


def test_admin_ai_jobs_service_gets_job_events() -> None:
    service = AdminAIJobsService(
        cast(Session, object()),
        ai_jobs_service=FakeAIJobsService(),
        queue=cast(AIJobQueue, object()),
    )

    response = service.list_job_events(JOB_ID)

    assert response.count == 1
    assert response.items[0].event_type == "created"


def test_admin_ai_jobs_service_records_cancel_operation() -> None:
    fake_ai_jobs = FakeAIJobsService()
    created: list[AdminOperationCreate] = []
    finished: list[AdminOperationUpdate] = []
    service = _service(fake_ai_jobs=fake_ai_jobs, created=created, finished=finished)

    response = service.cancel_job(JOB_ID, AdminAIJobActionRequest(actor="operator"))

    assert created[0].operation_type == "cancel_ai_job"
    assert created[0].request_payload == {"job_id": str(JOB_ID), "actor": "operator"}
    assert fake_ai_jobs.cancelled == [(JOB_ID, "operator")]
    assert finished[0].status == "succeeded"
    assert finished[0].result_summary["status"] == "cancelled"
    assert response.operation_id == OPERATION_ID
    assert (
        response.preview
        == f"figure-data cancel-ai-job --job-id {JOB_ID} --cancelled-by operator"
    )


def test_admin_ai_jobs_service_persists_failed_cancel_operation() -> None:
    created: list[AdminOperationCreate] = []
    finished: list[AdminOperationUpdate] = []
    session = TransactionTrackingSession()
    service = _service(
        fake_ai_jobs=FakeAIJobsService(fail_cancel=True),
        created=created,
        finished=finished,
        session=session,
    )

    with pytest.raises(ApplicationError):
        service.cancel_job(JOB_ID, AdminAIJobActionRequest(actor="operator"))

    assert created[0].operation_type == "cancel_ai_job"
    assert finished[0].status == "failed"
    assert finished[0].error_message == "cancel failed"
    assert session.events == ["commit", "rollback", "commit"]


def test_admin_ai_jobs_service_records_retry_operation() -> None:
    fake_ai_jobs = FakeAIJobsService()
    created: list[AdminOperationCreate] = []
    finished: list[AdminOperationUpdate] = []
    service = _service(fake_ai_jobs=fake_ai_jobs, created=created, finished=finished)

    response = service.retry_job(JOB_ID, AdminAIJobActionRequest(actor="operator"))

    assert created[0].operation_type == "retry_ai_job"
    assert fake_ai_jobs.retried == [(JOB_ID, "operator")]
    assert finished[0].status == "succeeded"
    assert response.preview == f"figure-data retry-ai-job --job-id {JOB_ID} --created-by operator"


def test_admin_ai_jobs_service_records_requeue_operation() -> None:
    created: list[AdminOperationCreate] = []
    finished: list[AdminOperationUpdate] = []
    service = _service(
        created=created,
        finished=finished,
        requeue_fn=lambda **kwargs: RequeueAIJobsResult(
            scanned=2,
            enqueued=1,
            failed=1,
            job_ids=[JOB_ID],
        ),
    )

    response = service.requeue_jobs(AdminAIJobsRequeueRequest(actor="operator", limit=20))

    assert created[0].operation_type == "requeue_ai_jobs"
    assert created[0].request_payload == {"actor": "operator", "limit": 20}
    assert finished[0].status == "succeeded"
    assert finished[0].result_summary == {
        "scanned": 2,
        "enqueued": 1,
        "failed": 1,
        "job_ids": [str(JOB_ID)],
    }
    assert response.preview == "figure-data requeue-ai-jobs --limit 20"


def test_admin_ai_jobs_service_returns_health() -> None:
    service = AdminAIJobsService(
        cast(Session, object()),
        ai_jobs_service=FakeAIJobsService(),
        queue=cast(AIJobQueue, object()),
    )

    response = service.get_health()

    assert response.queued_count == 2
    assert response.stale_running_count == 1


def _service(
    *,
    fake_ai_jobs: FakeAIJobsService | None = None,
    created: list[AdminOperationCreate],
    finished: list[AdminOperationUpdate],
    requeue_fn: Any | None = None,
    session: object | None = None,
) -> AdminAIJobsService:
    def create_operation(
        session: Session,
        operation: AdminOperationCreate,
    ) -> AdminOperationRecord:
        created.append(operation)
        return _operation(operation.operation_type)

    def mark_finished(
        session: Session,
        operation_id: UUID,
        update: AdminOperationUpdate,
    ) -> AdminOperationRecord:
        finished.append(update)
        return _operation("finished", status=update.status, result_summary=update.result_summary)

    return AdminAIJobsService(
        cast(Session, session or object()),
        ai_jobs_service=fake_ai_jobs or FakeAIJobsService(),
        queue=cast(AIJobQueue, object()),
        create_operation_fn=create_operation,
        mark_operation_finished_fn=mark_finished,
        requeue_fn=requeue_fn,
    )


class TransactionTrackingSession:
    def __init__(self) -> None:
        self.events: list[str] = []

    def commit(self) -> None:
        self.events.append("commit")

    def rollback(self) -> None:
        self.events.append("rollback")


def _job_response(*, id: UUID, status: str = "queued") -> AiJobResponse:
    return AiJobResponse(
        id=id,
        job_type="candidate_review_suggestion",
        target_type="candidate",
        target_kind="relationship",
        target_id=1,
        status=status,
        created_by="local",
        params={},
        result_ref_type=None,
        result_ref_id=None,
        error_code=None,
        error_message=None,
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
        started_at=None,
        finished_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _job_record(job_id: UUID) -> AIGenerationJobRecord:
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
        created_at=NOW,
        updated_at=NOW,
    )


def _operation(
    operation_type: str,
    *,
    status: str = "queued",
    result_summary: dict[str, Any] | None = None,
) -> AdminOperationRecord:
    return AdminOperationRecord(
        id=OPERATION_ID,
        operation_type=operation_type,
        actor="operator",
        status=status,
        request_payload={},
        result_summary=result_summary or {},
        error_message=None,
        related_resource_type="ai_generation_job",
        related_resource_id=str(JOB_ID),
        started_at=None,
        finished_at=None,
        created_at=NOW,
        updated_at=NOW,
    )
