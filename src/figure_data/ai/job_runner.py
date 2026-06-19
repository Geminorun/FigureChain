from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.ai.candidate_service import (
    CandidateReviewSuggestionResult,
    generate_candidate_review_suggestion,
)
from figure_data.ai.job_repository import (
    AIGenerationJobRecord,
    claim_queued_job_by_id,
    claim_queued_jobs,
    mark_failed,
    mark_succeeded,
    record_job_event,
)
from figure_data.config import Settings
from figure_data.review.types import CandidateKind, CandidateReviewError

ERROR_MESSAGE_LIMIT = 500


class AIGenerationJobRepository(Protocol):
    def claim_queued_jobs(
        self,
        session: Session,
        *,
        limit: int,
        job_type: str | None = None,
    ) -> list[AIGenerationJobRecord]:
        """Claim queued jobs and move them to running."""

    def claim_queued_job_by_id(
        self,
        session: Session,
        job_id: UUID,
        *,
        worker_id: str,
    ) -> AIGenerationJobRecord | None:
        """Claim a single queued job by id."""

    def mark_succeeded(
        self,
        session: Session,
        job_id: UUID,
        *,
        result_ref_type: str,
        result_ref_id: UUID,
    ) -> AIGenerationJobRecord:
        """Mark a running job as succeeded."""

    def mark_failed(
        self,
        session: Session,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> AIGenerationJobRecord:
        """Mark a running job as failed."""

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
        """Record a job event."""


class GenerateCandidateReviewSuggestionFn(Protocol):
    def __call__(
        self,
        *,
        session: Session,
        settings: Settings,
        kind: CandidateKind,
        candidate_id: int,
        created_by: str,
        retrieval_limit: int = 5,
    ) -> CandidateReviewSuggestionResult:
        """Generate and persist a candidate review suggestion."""


class PostgresAIGenerationJobRepository:
    def claim_queued_jobs(
        self,
        session: Session,
        *,
        limit: int,
        job_type: str | None = None,
    ) -> list[AIGenerationJobRecord]:
        return claim_queued_jobs(session, limit=limit, job_type=job_type)

    def claim_queued_job_by_id(
        self,
        session: Session,
        job_id: UUID,
        *,
        worker_id: str,
    ) -> AIGenerationJobRecord | None:
        return claim_queued_job_by_id(session, job_id, worker_id=worker_id)

    def mark_succeeded(
        self,
        session: Session,
        job_id: UUID,
        *,
        result_ref_type: str,
        result_ref_id: UUID,
    ) -> AIGenerationJobRecord:
        return mark_succeeded(
            session,
            job_id,
            result_ref_type=result_ref_type,
            result_ref_id=result_ref_id,
        )

    def mark_failed(
        self,
        session: Session,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> AIGenerationJobRecord:
        return mark_failed(
            session,
            job_id,
            error_code=error_code,
            error_message=error_message,
        )

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
        return record_job_event(
            session,
            job_id=job_id,
            event_type=event_type,
            actor=actor,
            message=message,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AIGenerationJobFailure:
    job_id: UUID
    error_code: str
    error_message: str


@dataclass(frozen=True)
class AIGenerationJobRunSummary:
    claimed_count: int
    succeeded_count: int
    failed_count: int
    failures: list[AIGenerationJobFailure]


@dataclass(frozen=True)
class AIGenerationJobExecutionResult:
    job_id: UUID
    status: str
    error_code: str | None = None
    error_message: str | None = None


def run_ai_jobs(
    *,
    session: Session,
    settings: Settings,
    limit: int,
    job_type: str | None = None,
    repository: AIGenerationJobRepository | None = None,
    generate_candidate_review_suggestion_fn: GenerateCandidateReviewSuggestionFn = (
        generate_candidate_review_suggestion
    ),
) -> AIGenerationJobRunSummary:
    resolved_repository = repository or PostgresAIGenerationJobRepository()
    jobs = resolved_repository.claim_queued_jobs(session, limit=limit, job_type=job_type)
    failures: list[AIGenerationJobFailure] = []
    succeeded_count = 0

    for job in jobs:
        try:
            result = _run_job(
                session=session,
                settings=settings,
                job=job,
                generate_candidate_review_suggestion_fn=generate_candidate_review_suggestion_fn,
            )
            resolved_repository.mark_succeeded(
                session,
                job.id,
                result_ref_type="ai_candidate_review_suggestion",
                result_ref_id=result.suggestion.id,
            )
            succeeded_count += 1
        except Exception as exc:
            error_code = _error_code(exc)
            error_message = _error_message(exc)
            resolved_repository.mark_failed(
                session,
                job.id,
                error_code=error_code,
                error_message=error_message,
            )
            failures.append(
                AIGenerationJobFailure(
                    job_id=job.id,
                    error_code=error_code,
                    error_message=error_message,
                )
            )

    return AIGenerationJobRunSummary(
        claimed_count=len(jobs),
        succeeded_count=succeeded_count,
        failed_count=len(failures),
        failures=failures,
    )


def execute_ai_job(
    *,
    session: Session,
    settings: Settings,
    job_id: UUID,
    worker_id: str,
    repository: AIGenerationJobRepository | None = None,
    generate_candidate_review_suggestion_fn: GenerateCandidateReviewSuggestionFn = (
        generate_candidate_review_suggestion
    ),
) -> AIGenerationJobExecutionResult:
    resolved_repository = repository or PostgresAIGenerationJobRepository()
    job = resolved_repository.claim_queued_job_by_id(
        session,
        job_id,
        worker_id=worker_id,
    )
    if job is None:
        return AIGenerationJobExecutionResult(job_id=job_id, status="skipped")

    resolved_repository.record_event(
        session,
        job_id=job.id,
        event_type="started",
        actor="worker",
        metadata={"worker_id": worker_id},
    )
    try:
        result = _run_job(
            session=session,
            settings=settings,
            job=job,
            generate_candidate_review_suggestion_fn=generate_candidate_review_suggestion_fn,
        )
        resolved_repository.mark_succeeded(
            session,
            job.id,
            result_ref_type="ai_candidate_review_suggestion",
            result_ref_id=result.suggestion.id,
        )
        resolved_repository.record_event(
            session,
            job_id=job.id,
            event_type="succeeded",
            actor="worker",
            metadata={"result_ref_id": str(result.suggestion.id)},
        )
        return AIGenerationJobExecutionResult(job_id=job.id, status="succeeded")
    except Exception as exc:
        error_code = _error_code(exc)
        error_message = _error_message(exc)
        resolved_repository.mark_failed(
            session,
            job.id,
            error_code=error_code,
            error_message=error_message,
        )
        resolved_repository.record_event(
            session,
            job_id=job.id,
            event_type="failed",
            actor="worker",
            message=error_message,
            metadata={"error_code": error_code},
        )
        return AIGenerationJobExecutionResult(
            job_id=job.id,
            status="failed",
            error_code=error_code,
            error_message=error_message,
        )


def _run_job(
    *,
    session: Session,
    settings: Settings,
    job: AIGenerationJobRecord,
    generate_candidate_review_suggestion_fn: GenerateCandidateReviewSuggestionFn,
) -> CandidateReviewSuggestionResult:
    if job.job_type != "candidate_review_suggestion":
        raise ValueError(f"unsupported AI job type: {job.job_type}")
    if job.target_type != "candidate":
        raise ValueError(f"unsupported AI job target type: {job.target_type}")
    kind = CandidateKind(job.target_kind)
    return generate_candidate_review_suggestion_fn(
        session=session,
        settings=settings,
        kind=kind,
        candidate_id=job.target_id,
        created_by=job.created_by,
        retrieval_limit=_retrieval_limit(job),
    )


def _retrieval_limit(job: AIGenerationJobRecord) -> int:
    value = job.params.get("retrieval_limit", 5)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return 5


def _error_code(exc: Exception) -> str:
    if isinstance(exc, CandidateReviewError):
        return "candidate_not_found"
    if isinstance(exc, ValueError) and str(exc).startswith("unsupported AI job"):
        return "ai_job_invalid_type"
    return "ai_job_execution_failed"


def _error_message(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    return message[:ERROR_MESSAGE_LIMIT]
