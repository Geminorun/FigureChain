from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.ai.candidate_service import (
    CandidateReviewSuggestionResult,
    generate_candidate_review_suggestion,
)
from figure_data.ai.job_rate_limit import AIJobRateLimiter
from figure_data.ai.job_repository import (
    AIGenerationJobRecord,
    claim_queued_job_by_id,
    claim_queued_jobs,
    mark_failed,
    mark_succeeded,
    record_job_event,
    schedule_job_retry,
)
from figure_data.config import Settings
from figure_data.review.types import CandidateKind, CandidateReviewError

ERROR_MESSAGE_LIMIT = 500
RETRYABLE_ERROR_CODES = {
    "provider_timeout",
    "provider_rate_limited",
    "provider_unavailable",
}


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

    def schedule_job_retry(
        self,
        session: Session,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
        delay_seconds: int,
    ) -> AIGenerationJobRecord:
        """Schedule a running job for retry."""

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

    def schedule_job_retry(
        self,
        session: Session,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
        delay_seconds: int,
    ) -> AIGenerationJobRecord:
        return schedule_job_retry(
            session,
            job_id,
            error_code=error_code,
            error_message=error_message,
            delay_seconds=delay_seconds,
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
    retry_delay_seconds: int | None = None
    retry_queue_job_id_suffix: str | None = None


@dataclass(frozen=True)
class AIJobRetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: int = 10

    def delay_for_attempt(self, attempt_count: int) -> int:
        exponent = max(attempt_count - 1, 0)
        return self.base_delay_seconds * (1 << exponent)


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
            if _is_retryable(error_code) and _can_retry(job):
                resolved_repository.schedule_job_retry(
                    session,
                    job.id,
                    error_code=error_code,
                    error_message=error_message,
                    delay_seconds=AIJobRetryPolicy(
                        max_attempts=job.max_attempts,
                        base_delay_seconds=int(
                            getattr(settings, "ai_job_retry_base_seconds", 10)
                        ),
                    ).delay_for_attempt(job.attempt_count),
                )
            else:
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
    rate_limiter: AIJobRateLimiter | None = None,
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
    rate_limit_result = _check_rate_limit(
        session=session,
        settings=settings,
        job=job,
        repository=resolved_repository,
        rate_limiter=rate_limiter,
    )
    if rate_limit_result is not None:
        return rate_limit_result

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
        if _is_retryable(error_code) and _can_retry(job):
            return _schedule_retry(
                session,
                settings=settings,
                job=job,
                repository=resolved_repository,
                error_code=error_code,
                error_message=error_message,
            )
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


def _check_rate_limit(
    *,
    session: Session,
    settings: Settings,
    job: AIGenerationJobRecord,
    repository: AIGenerationJobRepository,
    rate_limiter: AIJobRateLimiter | None,
) -> AIGenerationJobExecutionResult | None:
    if rate_limiter is None:
        return None

    provider_name = str(getattr(settings, "ai_provider", None) or "unknown")
    model_name = str(getattr(settings, "ai_model", None) or "unknown")
    limit_per_minute = int(getattr(settings, "ai_rate_limit_per_minute", 20))
    if rate_limiter.allow(provider_name, model_name, limit_per_minute=limit_per_minute):
        return None

    error_code = "provider_rate_limited"
    error_message = "provider rate limit reached"
    if _can_retry(job):
        return _schedule_retry(
            session,
            settings=settings,
            job=job,
            repository=repository,
            error_code=error_code,
            error_message=error_message,
        )
    repository.mark_failed(
        session,
        job.id,
        error_code=error_code,
        error_message=error_message,
    )
    repository.record_event(
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


def _schedule_retry(
    session: Session,
    *,
    settings: Settings,
    job: AIGenerationJobRecord,
    repository: AIGenerationJobRepository,
    error_code: str,
    error_message: str,
) -> AIGenerationJobExecutionResult:
    delay_seconds = AIJobRetryPolicy(
        max_attempts=job.max_attempts,
        base_delay_seconds=int(getattr(settings, "ai_job_retry_base_seconds", 10)),
    ).delay_for_attempt(job.attempt_count)
    repository.schedule_job_retry(
        session,
        job.id,
        error_code=error_code,
        error_message=error_message,
        delay_seconds=delay_seconds,
    )
    repository.record_event(
        session,
        job_id=job.id,
        event_type="retry_scheduled",
        actor="worker",
        message=error_message,
        metadata={"delay_seconds": delay_seconds, "error_code": error_code},
    )
    return AIGenerationJobExecutionResult(
        job_id=job.id,
        status="retry_scheduled",
        error_code=error_code,
        error_message=error_message,
        retry_delay_seconds=delay_seconds,
        retry_queue_job_id_suffix=f"retry-{job.attempt_count}",
    )


def _can_retry(job: AIGenerationJobRecord) -> bool:
    return job.attempt_count < job.max_attempts


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
    message = str(exc).lower()
    if "provider_timeout" in message or "timeout" in message:
        return "provider_timeout"
    if "provider_rate_limited" in message or "rate limit" in message:
        return "provider_rate_limited"
    if "provider_unavailable" in message or "unavailable" in message:
        return "provider_unavailable"
    return "ai_job_execution_failed"


def _is_retryable(error_code: str) -> bool:
    return error_code in RETRYABLE_ERROR_CODES


def _error_message(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    return message[:ERROR_MESSAGE_LIMIT]
