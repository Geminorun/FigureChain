from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import AiJobCreateRequest
from figure_chain.services.ai_jobs import AIJobsService
from figure_data.ai.job_repository import AIGenerationJobRecord, NewAIGenerationJob
from figure_data.review.types import CandidateDetail, CandidateKind, CandidateReviewError

JOB_ID = UUID("00000000-0000-0000-0000-000000000501")


class FakeJobRepository:
    def __init__(self) -> None:
        self.created: list[NewAIGenerationJob] = []
        self.records: dict[UUID, AIGenerationJobRecord] = {JOB_ID: _job_record()}

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


def _job_record() -> AIGenerationJobRecord:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return AIGenerationJobRecord(
        id=JOB_ID,
        job_type="candidate_review_suggestion",
        target_type="candidate",
        target_kind="relationship",
        target_id=960698,
        status="queued",
        created_by="lyl",
        params={"retrieval_limit": 3},
        result_ref_type=None,
        result_ref_id=None,
        error_code=None,
        error_message=None,
        started_at=None,
        finished_at=None,
        created_at=now,
        updated_at=now,
    )
