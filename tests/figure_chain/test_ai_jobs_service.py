from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import AiJobCreateRequest
from figure_chain.services.ai_jobs import AIJobsService
from figure_data.ai.job_repository import (
    AIGenerationJobRecord,
    AIJobEventRecord,
    AIJobQueueHealthRecord,
    NewAIGenerationJob,
)
from figure_data.ai.queue import EnqueuedAIJob
from figure_data.review.types import CandidateDetail, CandidateKind, CandidateReviewError

JOB_ID = UUID("00000000-0000-0000-0000-000000000501")


class FakeJobRepository:
    def __init__(self) -> None:
        self.created: list[NewAIGenerationJob] = []
        self.records: dict[UUID, AIGenerationJobRecord] = {JOB_ID: _job_record()}
        self.enqueued: list[tuple[UUID, str, str, str]] = []
        self.events: list[tuple[UUID, str]] = []

    def create_job(self, session: Session, job: NewAIGenerationJob) -> UUID:
        self.created.append(job)
        return JOB_ID

    def get_job(self, session: Session, job_id: UUID) -> AIGenerationJobRecord | None:
        return self.records.get(job_id)

    def list_jobs_for_target(
        self,
        session: Session,
        *,
        target_type: str,
        target_kind: str,
        target_id: int,
        limit: int,
    ) -> list[AIGenerationJobRecord]:
        assert target_type == "candidate"
        assert target_kind == "relationship"
        assert target_id == 960698
        assert limit == 10
        return list(self.records.values())

    def mark_enqueued(
        self,
        session: Session,
        job_id: UUID,
        *,
        queue_backend: str,
        queue_name: str,
        queue_job_id: str,
    ) -> AIGenerationJobRecord:
        self.enqueued.append((job_id, queue_backend, queue_name, queue_job_id))
        return self.records[job_id]

    def record_event(
        self,
        session: Session,
        *,
        job_id: UUID,
        event_type: str,
        actor: str,
        message: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> UUID:
        self.events.append((job_id, event_type))
        return job_id

    def cancel_job(
        self,
        session: Session,
        job_id: UUID,
        *,
        cancelled_by: str,
    ) -> AIGenerationJobRecord:
        record = self.records[job_id]
        status = "cancelled" if record.status == "queued" else record.status
        cancelled = _job_record(status=status)
        self.records[job_id] = cancelled
        return cancelled

    def list_job_events(self, session: Session, job_id: UUID) -> list[AIJobEventRecord]:
        assert job_id == JOB_ID
        return [_job_event()]

    def get_queue_health(
        self,
        session: Session,
        *,
        stale_after_seconds: int,
    ) -> AIJobQueueHealthRecord:
        assert stale_after_seconds == 300
        return AIJobQueueHealthRecord(
            status_counts={"queued": 1},
            queued_count=1,
            running_count=0,
            succeeded_count=0,
            failed_count=0,
            cancelled_count=0,
            stale_running_count=0,
            oldest_queued_at=datetime(2026, 6, 18, tzinfo=UTC),
        )


class FakeQueue:
    def enqueue(self, job_id: UUID, *, queue_name: str, timeout_seconds: int) -> EnqueuedAIJob:
        return EnqueuedAIJob(
            queue_backend="rq",
            queue_name=queue_name,
            queue_job_id="rq-job-501",
        )


def test_ai_jobs_service_creates_queued_job_without_running_model() -> None:
    repository = FakeJobRepository()
    detail_calls: list[tuple[CandidateKind, int]] = []

    def get_detail(session: Session, kind: CandidateKind, candidate_id: int) -> CandidateDetail:
        detail_calls.append((kind, candidate_id))
        return cast(CandidateDetail, object())

    service = AIJobsService(
        cast(Session, object()),
        repository=repository,
        get_candidate_detail_fn=get_detail,
    )

    response = service.create_job(
        AiJobCreateRequest(
            job_type="candidate_review_suggestion",
            target_type="candidate",
            target_kind="relationship",
            target_id=960698,
            created_by="lyl",
            params={"retrieval_limit": 3},
        )
    )

    assert detail_calls == [(CandidateKind.RELATIONSHIP, 960698)]
    assert repository.created[0].job_type == "candidate_review_suggestion"
    assert repository.created[0].params == {"retrieval_limit": 3}
    assert response.id == JOB_ID
    assert response.status == "queued"


def test_ai_jobs_service_gets_job() -> None:
    service = AIJobsService(cast(Session, object()), repository=FakeJobRepository())

    response = service.get_job(JOB_ID)

    assert response.id == JOB_ID
    assert response.target_kind == "relationship"
    assert response.queue_backend == "database"
    assert response.attempt_count == 0
    assert response.worker_id is None


def test_ai_jobs_service_enqueues_after_creating_job() -> None:
    repository = FakeJobRepository()
    session = cast(Session, object())
    service = AIJobsService(
        session,
        repository=repository,
        queue=FakeQueue(),
        queue_name="figure-ai",
        job_timeout_seconds=120,
        get_candidate_detail_fn=lambda session, kind, candidate_id: cast(CandidateDetail, object()),
    )

    response = service.create_job(
        AiJobCreateRequest(
            job_type="candidate_review_suggestion",
            target_type="candidate",
            target_kind="relationship",
            target_id=960698,
            created_by="lyl",
            params={"retrieval_limit": 3},
        )
    )

    assert response.status == "queued"
    assert repository.enqueued == [(JOB_ID, "rq", "figure-ai", "rq-job-501")]
    assert repository.events[-1] == (JOB_ID, "enqueued")


def test_ai_jobs_service_lists_target_jobs() -> None:
    service = AIJobsService(cast(Session, object()), repository=FakeJobRepository())

    response = service.list_jobs(
        target_type="candidate",
        target_kind="relationship",
        target_id=960698,
        limit=10,
    )

    assert response.count == 1
    assert response.items[0].id == JOB_ID


def test_ai_jobs_service_cancels_job() -> None:
    repository = FakeJobRepository()
    service = AIJobsService(cast(Session, object()), repository=repository)

    response = service.cancel_job(JOB_ID, cancelled_by="lyl")

    assert response.id == JOB_ID
    assert response.status == "cancelled"
    assert repository.events[-1] == (JOB_ID, "cancel_requested")


def test_ai_jobs_service_retries_job_by_creating_new_job() -> None:
    repository = FakeJobRepository()
    service = AIJobsService(
        cast(Session, object()),
        repository=repository,
        get_candidate_detail_fn=lambda session, kind, candidate_id: cast(CandidateDetail, object()),
    )

    response = service.retry_job(JOB_ID, created_by="lyl")

    assert response.id == JOB_ID
    assert repository.created[-1].params["retry_of_job_id"] == str(JOB_ID)


def test_ai_jobs_service_lists_job_events() -> None:
    service = AIJobsService(cast(Session, object()), repository=FakeJobRepository())

    response = service.list_job_events(JOB_ID)

    assert response.count == 1
    assert response.items[0].event_type == "created"


def test_ai_jobs_service_reports_queue_health() -> None:
    service = AIJobsService(cast(Session, object()), repository=FakeJobRepository())

    response = service.get_queue_health(stale_after_seconds=300)

    assert response.status_counts == {"queued": 1}
    assert response.queued_count == 1


def test_ai_jobs_service_maps_missing_job_to_application_error() -> None:
    repository = FakeJobRepository()
    repository.records = {}
    service = AIJobsService(cast(Session, object()), repository=repository)

    with pytest.raises(ApplicationError) as exc_info:
        service.get_job(JOB_ID)

    assert exc_info.value.code is ErrorCode.AI_JOB_NOT_FOUND
    assert exc_info.value.details == {"job_id": str(JOB_ID)}


def test_ai_jobs_service_rejects_invalid_job_type() -> None:
    service = AIJobsService(cast(Session, object()), repository=FakeJobRepository())

    with pytest.raises(ApplicationError) as exc_info:
        service.create_job(
            AiJobCreateRequest(
                job_type="chain_explanation",
                target_type="candidate",
                target_kind="relationship",
                target_id=960698,
                created_by="lyl",
            )
        )

    assert exc_info.value.code is ErrorCode.AI_JOB_INVALID_TYPE
    assert exc_info.value.details == {"job_type": "chain_explanation"}


def test_ai_jobs_service_maps_missing_candidate_to_application_error() -> None:
    def get_detail(session: Session, kind: CandidateKind, candidate_id: int) -> CandidateDetail:
        raise CandidateReviewError("candidate not found")

    service = AIJobsService(
        cast(Session, object()),
        repository=FakeJobRepository(),
        get_candidate_detail_fn=get_detail,
    )

    with pytest.raises(ApplicationError) as exc_info:
        service.create_job(
            AiJobCreateRequest(
                job_type="candidate_review_suggestion",
                target_type="candidate",
                target_kind="relationship",
                target_id=960698,
                created_by="lyl",
            )
        )

    assert exc_info.value.code is ErrorCode.CANDIDATE_NOT_FOUND
    assert exc_info.value.details == {"kind": "relationship", "candidate_id": 960698}


def _job_record(*, status: str = "queued") -> AIGenerationJobRecord:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return AIGenerationJobRecord(
        id=JOB_ID,
        job_type="candidate_review_suggestion",
        target_type="candidate",
        target_kind="relationship",
        target_id=960698,
        status=status,
        created_by="lyl",
        params={"retrieval_limit": 3},
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


def _job_event() -> AIJobEventRecord:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return AIJobEventRecord(
        id=UUID("00000000-0000-0000-0000-000000000601"),
        job_id=JOB_ID,
        event_type="created",
        actor="api",
        message="AI job created",
        metadata={"job_type": "candidate_review_suggestion"},
        created_at=now,
    )
