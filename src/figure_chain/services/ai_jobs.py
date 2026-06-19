from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import AiJobCreateRequest, AiJobListResponse, AiJobResponse
from figure_data.ai.job_repository import (
    AIGenerationJobRecord,
    NewAIGenerationJob,
    create_job,
    get_job,
    list_jobs_for_target,
    mark_enqueued,
    record_job_event,
)
from figure_data.ai.queue import AIJobQueue
from figure_data.review.candidate_detail import get_candidate_detail
from figure_data.review.types import (
    CandidateDetail,
    CandidateKind,
    CandidateReviewError,
    normalize_candidate_kind,
)

SUPPORTED_JOB_TYPE = "candidate_review_suggestion"
SUPPORTED_TARGET_TYPE = "candidate"

GetCandidateDetailFn = Callable[[Session, CandidateKind, int], CandidateDetail]


class AIJobRepository(Protocol):
    def create_job(self, session: Session, job: NewAIGenerationJob) -> UUID:
        """Create a queued AI job."""

    def get_job(self, session: Session, job_id: UUID) -> AIGenerationJobRecord | None:
        """Load an AI job."""

    def list_jobs_for_target(
        self,
        session: Session,
        *,
        target_type: str,
        target_kind: str,
        target_id: int,
        limit: int,
    ) -> list[AIGenerationJobRecord]:
        """List AI jobs for one target."""

    def mark_enqueued(
        self,
        session: Session,
        job_id: UUID,
        *,
        queue_backend: str,
        queue_name: str,
        queue_job_id: str,
    ) -> AIGenerationJobRecord:
        """Persist queue metadata after enqueue."""

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
        """Record an AI job event."""


class PostgresAIJobRepository:
    def create_job(self, session: Session, job: NewAIGenerationJob) -> UUID:
        return create_job(session, job)

    def get_job(self, session: Session, job_id: UUID) -> AIGenerationJobRecord | None:
        return get_job(session, job_id)

    def list_jobs_for_target(
        self,
        session: Session,
        *,
        target_type: str,
        target_kind: str,
        target_id: int,
        limit: int,
    ) -> list[AIGenerationJobRecord]:
        return list_jobs_for_target(
            session,
            target_type=target_type,
            target_kind=target_kind,
            target_id=target_id,
            limit=limit,
        )

    def mark_enqueued(
        self,
        session: Session,
        job_id: UUID,
        *,
        queue_backend: str,
        queue_name: str,
        queue_job_id: str,
    ) -> AIGenerationJobRecord:
        return mark_enqueued(
            session,
            job_id,
            queue_backend=queue_backend,
            queue_name=queue_name,
            queue_job_id=queue_job_id,
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


class AIJobsService:
    def __init__(
        self,
        session: Session,
        *,
        repository: AIJobRepository | None = None,
        queue: AIJobQueue | None = None,
        queue_name: str = "figure-ai",
        job_timeout_seconds: int = 120,
        get_candidate_detail_fn: GetCandidateDetailFn = get_candidate_detail,
    ) -> None:
        self._session = session
        self._repository = repository or PostgresAIJobRepository()
        self._queue = queue
        self._queue_name = queue_name
        self._job_timeout_seconds = job_timeout_seconds
        self._get_candidate_detail_fn = get_candidate_detail_fn

    def create_job(self, request: AiJobCreateRequest) -> AiJobResponse:
        self._validate_job_type(request.job_type)
        self._validate_target_type(request.target_type)
        kind = self._normalize_kind(request.target_kind)
        self._ensure_candidate_exists(kind, request.target_id)
        job_id = self._repository.create_job(
            self._session,
            NewAIGenerationJob(
                job_type=request.job_type,
                target_type=request.target_type,
                target_kind=kind.value,
                target_id=request.target_id,
                created_by=request.created_by,
                params=request.params,
            ),
        )
        self._repository.record_event(
            self._session,
            job_id=job_id,
            event_type="created",
            actor="api",
            message="AI job created",
            metadata={"job_type": request.job_type},
        )
        self._commit_if_supported()
        if self._queue is not None:
            try:
                enqueued = self._queue.enqueue(
                    job_id,
                    queue_name=self._queue_name,
                    timeout_seconds=self._job_timeout_seconds,
                )
                if enqueued.queue_job_id is not None:
                    self._repository.mark_enqueued(
                        self._session,
                        job_id,
                        queue_backend=enqueued.queue_backend,
                        queue_name=enqueued.queue_name,
                        queue_job_id=enqueued.queue_job_id,
                    )
                self._repository.record_event(
                    self._session,
                    job_id=job_id,
                    event_type="enqueued",
                    actor="api",
                    message="AI job enqueued",
                    metadata={"queue_backend": enqueued.queue_backend},
                )
            except Exception as exc:
                self._repository.record_event(
                    self._session,
                    job_id=job_id,
                    event_type="enqueue_failed",
                    actor="api",
                    message=str(exc)[:200],
                    metadata={"queue_name": self._queue_name},
                )
        self._commit_if_supported()
        record = self._repository.get_job(self._session, job_id)
        if record is None:
            raise ApplicationError(
                code=ErrorCode.AI_JOB_NOT_FOUND,
                message="AI job was not found after creation",
                details={"job_id": str(job_id)},
            )
        return self._job(record)

    def _commit_if_supported(self) -> None:
        commit = getattr(self._session, "commit", None)
        if callable(commit):
            commit()

    def get_job(self, job_id: UUID) -> AiJobResponse:
        record = self._repository.get_job(self._session, job_id)
        if record is None:
            raise ApplicationError(
                code=ErrorCode.AI_JOB_NOT_FOUND,
                message="AI job was not found",
                details={"job_id": str(job_id)},
            )
        return self._job(record)

    def list_jobs(
        self,
        *,
        target_type: str,
        target_kind: str,
        target_id: int,
        limit: int,
    ) -> AiJobListResponse:
        self._validate_target_type(target_type)
        kind = self._normalize_kind(target_kind)
        records = self._repository.list_jobs_for_target(
            self._session,
            target_type=target_type,
            target_kind=kind.value,
            target_id=target_id,
            limit=limit,
        )
        return AiJobListResponse(
            items=[self._job(record) for record in records],
            count=len(records),
            limit=limit,
        )

    def _validate_job_type(self, job_type: str) -> None:
        if job_type != SUPPORTED_JOB_TYPE:
            raise ApplicationError(
                code=ErrorCode.AI_JOB_INVALID_TYPE,
                message="AI job type is not supported",
                details={"job_type": job_type},
            )

    def _validate_target_type(self, target_type: str) -> None:
        if target_type != SUPPORTED_TARGET_TYPE:
            raise ApplicationError(
                code=ErrorCode.AI_JOB_INVALID_TYPE,
                message="AI job target type is not supported",
                details={"target_type": target_type},
            )

    def _normalize_kind(self, target_kind: str) -> CandidateKind:
        try:
            return normalize_candidate_kind(target_kind)
        except CandidateReviewError as exc:
            raise ApplicationError(
                code=ErrorCode.CANDIDATE_INVALID_KIND,
                message="candidate kind is not supported",
                details={"kind": target_kind},
            ) from exc

    def _ensure_candidate_exists(self, kind: CandidateKind, candidate_id: int) -> None:
        try:
            self._get_candidate_detail_fn(self._session, kind, candidate_id)
        except CandidateReviewError as exc:
            raise ApplicationError(
                code=ErrorCode.CANDIDATE_NOT_FOUND,
                message="candidate was not found",
                details={"kind": kind.value, "candidate_id": candidate_id},
            ) from exc

    def _job(self, record: AIGenerationJobRecord) -> AiJobResponse:
        return AiJobResponse(
            id=record.id,
            job_type=record.job_type,
            target_type=record.target_type,
            target_kind=record.target_kind,
            target_id=record.target_id,
            status=record.status,
            created_by=record.created_by,
            params=record.params,
            result_ref_type=record.result_ref_type,
            result_ref_id=record.result_ref_id,
            error_code=record.error_code,
            error_message=record.error_message,
            started_at=record.started_at,
            finished_at=record.finished_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
