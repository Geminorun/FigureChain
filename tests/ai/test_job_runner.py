from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.ai.candidate_repository import CandidateSuggestionRecord
from figure_data.ai.candidate_service import CandidateReviewSuggestionResult
from figure_data.ai.job_repository import AIGenerationJobRecord
from figure_data.ai.job_runner import run_ai_jobs
from figure_data.config import Settings
from figure_data.review.types import CandidateKind, CandidateReviewError

JOB_ID = UUID("00000000-0000-0000-0000-000000000501")
SUGGESTION_ID = UUID("00000000-0000-0000-0000-000000000701")
AI_RUN_ID = UUID("00000000-0000-0000-0000-000000000801")


class FakeJobRepository:
    def __init__(self, jobs: list[AIGenerationJobRecord]) -> None:
        self.jobs = jobs
        self.succeeded: list[tuple[UUID, str, UUID]] = []
        self.failed: list[tuple[UUID, str, str]] = []
        self.claimed_limit: int | None = None
        self.claimed_job_type: str | None = None

    def claim_queued_jobs(
        self,
        session: Session,
        *,
        limit: int,
        job_type: str | None = None,
    ) -> list[AIGenerationJobRecord]:
        self.claimed_limit = limit
        self.claimed_job_type = job_type
        return self.jobs

    def mark_succeeded(
        self,
        session: Session,
        job_id: UUID,
        *,
        result_ref_type: str,
        result_ref_id: UUID,
    ) -> AIGenerationJobRecord:
        self.succeeded.append((job_id, result_ref_type, result_ref_id))
        return self.jobs[0]

    def mark_failed(
        self,
        session: Session,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> AIGenerationJobRecord:
        self.failed.append((job_id, error_code, error_message))
        return self.jobs[0]


def test_run_ai_jobs_executes_candidate_review_job_and_marks_success() -> None:
    repository = FakeJobRepository([_job()])
    calls: list[tuple[CandidateKind, int, str, int]] = []

    def generate(**kwargs: object) -> CandidateReviewSuggestionResult:
        calls.append(
            (
                cast(CandidateKind, kwargs["kind"]),
                cast(int, kwargs["candidate_id"]),
                cast(str, kwargs["created_by"]),
                cast(int, kwargs["retrieval_limit"]),
            )
        )
        return CandidateReviewSuggestionResult(
            ai_run_id=AI_RUN_ID,
            suggestion=_suggestion(),
        )

    summary = run_ai_jobs(
        session=cast(Session, object()),
        settings=cast(Settings, object()),
        limit=10,
        job_type="candidate_review_suggestion",
        repository=repository,
        generate_candidate_review_suggestion_fn=generate,
    )

    assert repository.claimed_limit == 10
    assert repository.claimed_job_type == "candidate_review_suggestion"
    assert calls == [(CandidateKind.RELATIONSHIP, 960698, "lyl", 3)]
    assert repository.succeeded == [
        (JOB_ID, "ai_candidate_review_suggestion", SUGGESTION_ID)
    ]
    assert repository.failed == []
    assert summary.claimed_count == 1
    assert summary.succeeded_count == 1
    assert summary.failed_count == 0


def test_run_ai_jobs_marks_candidate_error_failed() -> None:
    repository = FakeJobRepository([_job()])

    def generate(**kwargs: object) -> CandidateReviewSuggestionResult:
        raise CandidateReviewError("candidate not found")

    summary = run_ai_jobs(
        session=cast(Session, object()),
        settings=cast(Settings, object()),
        limit=1,
        repository=repository,
        generate_candidate_review_suggestion_fn=generate,
    )

    assert repository.succeeded == []
    assert repository.failed[0][0] == JOB_ID
    assert repository.failed[0][1] == "candidate_not_found"
    assert "candidate not found" in repository.failed[0][2]
    assert summary.failed_count == 1
    assert summary.failures[0].error_code == "candidate_not_found"


def test_run_ai_jobs_marks_model_exception_failed_without_stack_trace() -> None:
    repository = FakeJobRepository([_job()])

    def generate(**kwargs: object) -> CandidateReviewSuggestionResult:
        raise RuntimeError("provider exploded")

    summary = run_ai_jobs(
        session=cast(Session, object()),
        settings=cast(Settings, object()),
        limit=1,
        repository=repository,
        generate_candidate_review_suggestion_fn=generate,
    )

    assert repository.failed[0][1] == "ai_job_execution_failed"
    assert repository.failed[0][2] == "provider exploded"
    assert "Traceback" not in repository.failed[0][2]
    assert summary.failed_count == 1


def test_run_ai_jobs_does_not_change_candidate_review_state() -> None:
    repository = FakeJobRepository([_job()])
    candidate_status_calls: list[str] = []

    def generate(**kwargs: object) -> CandidateReviewSuggestionResult:
        candidate_status_calls.append("generate_only")
        return CandidateReviewSuggestionResult(
            ai_run_id=AI_RUN_ID,
            suggestion=_suggestion(),
        )

    run_ai_jobs(
        session=cast(Session, object()),
        settings=cast(Settings, object()),
        limit=1,
        repository=repository,
        generate_candidate_review_suggestion_fn=generate,
    )

    assert candidate_status_calls == ["generate_only"]
    assert repository.succeeded
    assert repository.failed == []


def _job() -> AIGenerationJobRecord:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return AIGenerationJobRecord(
        id=JOB_ID,
        job_type="candidate_review_suggestion",
        target_type="candidate",
        target_kind="relationship",
        target_id=960698,
        status="running",
        created_by="lyl",
        params={"retrieval_limit": 3},
        result_ref_type=None,
        result_ref_id=None,
        error_code=None,
        error_message=None,
        started_at=now,
        finished_at=None,
        created_at=now,
        updated_at=now,
    )


def _suggestion() -> CandidateSuggestionRecord:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return CandidateSuggestionRecord(
        id=SUGGESTION_ID,
        ai_run_id=AI_RUN_ID,
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        suggested_action="needs_human_review",
        priority_score=70,
        evidence_summary_draft="需要人工复核",
        risk_flags=[],
        supporting_source_ref_ids=[],
        review_questions=[],
        explanation="基于来源证据。",
        status="generated",
        reviewed_by=None,
        reviewed_at=None,
        review_note=None,
        created_at=now,
    )
