from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    AdminAIJobActionRequest,
    AdminAIJobActionResponse,
    AdminAIJobListResponse,
    AdminAIJobsRequeueRequest,
    AiJobEventListResponse,
    AiJobHealthResponse,
    AiJobResponse,
)
from figure_chain.services.ai_jobs import AIJobsService
from figure_data.admin.operations import (
    AdminOperationCreate,
    AdminOperationRecord,
    AdminOperationUpdate,
    create_admin_operation,
    mark_admin_operation_finished,
)
from figure_data.ai.job_repository import (
    AIGenerationJobRecord,
    AIJobListFilters,
    list_jobs,
)
from figure_data.ai.queue import AIJobQueue
from figure_data.ai.redaction import redact_sensitive_text
from figure_data.ai.requeue import RequeueAIJobsResult, requeue_ai_jobs

ListJobsFn = Callable[[Session, AIJobListFilters], list[AIGenerationJobRecord]]
CreateOperationFn = Callable[[Session, AdminOperationCreate], AdminOperationRecord]
MarkOperationFinishedFn = Callable[[Session, UUID, AdminOperationUpdate], AdminOperationRecord]
RequeueFn = Callable[..., RequeueAIJobsResult]


class AdminAIJobsServiceBackend(Protocol):
    def get_job(self, job_id: UUID) -> AiJobResponse: ...

    def list_job_events(self, job_id: UUID) -> AiJobEventListResponse: ...

    def cancel_job(self, job_id: UUID, *, cancelled_by: str) -> AiJobResponse: ...

    def retry_job(self, job_id: UUID, *, created_by: str) -> AiJobResponse: ...

    def get_queue_health(self) -> AiJobHealthResponse: ...


class AdminAIJobsService:
    def __init__(
        self,
        session: Session,
        *,
        ai_jobs_service: AdminAIJobsServiceBackend | None = None,
        queue: AIJobQueue | None,
        queue_name: str = "figure-ai",
        job_timeout_seconds: int = 120,
        list_jobs_fn: ListJobsFn = list_jobs,
        create_operation_fn: CreateOperationFn = create_admin_operation,
        mark_operation_finished_fn: MarkOperationFinishedFn = mark_admin_operation_finished,
        requeue_fn: RequeueFn | None = None,
    ) -> None:
        self._session = session
        self._ai_jobs_service = ai_jobs_service or AIJobsService(session)
        self._queue = queue
        self._queue_name = queue_name
        self._job_timeout_seconds = job_timeout_seconds
        self._list_jobs_fn = list_jobs_fn
        self._create_operation_fn = create_operation_fn
        self._mark_operation_finished_fn = mark_operation_finished_fn
        self._requeue_fn = requeue_fn or requeue_ai_jobs

    def list_jobs(
        self,
        *,
        status: str | None = None,
        target_kind: str | None = None,
        target_id: int | None = None,
        queue_backend: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AdminAIJobListResponse:
        filters = AIJobListFilters(
            status=status,
            target_kind=target_kind,
            target_id=target_id,
            queue_backend=queue_backend,
            limit=limit,
            offset=offset,
        )
        records = self._list_jobs_fn(self._session, filters)
        return AdminAIJobListResponse(
            items=[self._job(record) for record in records],
            count=len(records),
            limit=min(max(limit, 1), 100),
            offset=max(offset, 0),
        )

    def get_job(self, job_id: UUID) -> AiJobResponse:
        return self._ai_jobs_service.get_job(job_id)

    def list_job_events(self, job_id: UUID) -> AiJobEventListResponse:
        return self._ai_jobs_service.list_job_events(job_id)

    def get_health(self) -> AiJobHealthResponse:
        return self._ai_jobs_service.get_queue_health()

    def cancel_job(
        self,
        job_id: UUID,
        request: AdminAIJobActionRequest,
    ) -> AdminAIJobActionResponse:
        operation = self._create_operation(
            operation_type="cancel_ai_job",
            actor=request.actor,
            request_payload={"job_id": str(job_id), "actor": request.actor},
            related_resource_id=str(job_id),
        )
        _commit_if_supported(self._session)
        preview = f"figure-data cancel-ai-job --job-id {job_id} --cancelled-by {request.actor}"
        try:
            job = self._ai_jobs_service.cancel_job(job_id, cancelled_by=request.actor)
            summary: dict[str, object] = {"job_id": str(job_id), "status": job.status}
            finished = self._finish_operation(operation.id, status="succeeded", summary=summary)
            return AdminAIJobActionResponse(
                operation_id=operation.id,
                operation_type=operation.operation_type,
                status=finished.status,
                job=job,
                result_summary=summary,
                preview=preview,
            )
        except Exception as exc:
            _rollback_if_supported(self._session)
            self._finish_failed_operation(operation.id, exc)
            _commit_if_supported(self._session)
            raise _application_error(exc) from exc

    def retry_job(
        self,
        job_id: UUID,
        request: AdminAIJobActionRequest,
    ) -> AdminAIJobActionResponse:
        operation = self._create_operation(
            operation_type="retry_ai_job",
            actor=request.actor,
            request_payload={"job_id": str(job_id), "actor": request.actor},
            related_resource_id=str(job_id),
        )
        _commit_if_supported(self._session)
        preview = f"figure-data retry-ai-job --job-id {job_id} --created-by {request.actor}"
        try:
            job = self._ai_jobs_service.retry_job(job_id, created_by=request.actor)
            summary: dict[str, object] = {
                "job_id": str(job.id),
                "status": job.status,
                "retry_of_job_id": str(job_id),
            }
            finished = self._finish_operation(operation.id, status="succeeded", summary=summary)
            return AdminAIJobActionResponse(
                operation_id=operation.id,
                operation_type=operation.operation_type,
                status=finished.status,
                job=job,
                result_summary=summary,
                preview=preview,
            )
        except Exception as exc:
            _rollback_if_supported(self._session)
            self._finish_failed_operation(operation.id, exc)
            _commit_if_supported(self._session)
            raise _application_error(exc) from exc

    def requeue_jobs(self, request: AdminAIJobsRequeueRequest) -> AdminAIJobActionResponse:
        operation = self._create_operation(
            operation_type="requeue_ai_jobs",
            actor=request.actor,
            request_payload={"actor": request.actor, "limit": request.limit},
            related_resource_type="ai_generation_jobs",
            related_resource_id=None,
        )
        _commit_if_supported(self._session)
        preview = f"figure-data requeue-ai-jobs --limit {request.limit}"
        try:
            if self._queue is None:
                raise ApplicationError(
                    code=ErrorCode.CONFIGURATION_ERROR,
                    message="AI job queue is not configured",
                )
            result = self._requeue_fn(
                session=self._session,
                queue=self._queue,
                actor=request.actor,
                limit=request.limit,
                queue_name=self._queue_name,
                timeout_seconds=self._job_timeout_seconds,
            )
            summary = _requeue_summary(result)
            finished = self._finish_operation(operation.id, status="succeeded", summary=summary)
            return AdminAIJobActionResponse(
                operation_id=operation.id,
                operation_type=operation.operation_type,
                status=finished.status,
                job=None,
                result_summary=summary,
                preview=preview,
            )
        except Exception as exc:
            _rollback_if_supported(self._session)
            self._finish_failed_operation(operation.id, exc)
            _commit_if_supported(self._session)
            raise _application_error(exc) from exc

    def _create_operation(
        self,
        *,
        operation_type: str,
        actor: str,
        request_payload: dict[str, object],
        related_resource_id: str | None,
        related_resource_type: str = "ai_generation_job",
    ) -> AdminOperationRecord:
        return self._create_operation_fn(
            self._session,
            AdminOperationCreate(
                operation_type=operation_type,
                actor=actor,
                request_payload=request_payload,
                related_resource_type=related_resource_type,
                related_resource_id=related_resource_id,
            ),
        )

    def _finish_operation(
        self,
        operation_id: UUID,
        *,
        status: str,
        summary: dict[str, object],
    ) -> AdminOperationRecord:
        return self._mark_operation_finished_fn(
            self._session,
            operation_id,
            AdminOperationUpdate(status=status, result_summary=summary),
        )

    def _finish_failed_operation(self, operation_id: UUID, exc: Exception) -> AdminOperationRecord:
        return self._mark_operation_finished_fn(
            self._session,
            operation_id,
            AdminOperationUpdate(
                status="failed",
                result_summary={},
                error_message=redact_sensitive_text(str(exc)),
            ),
        )

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
            queue_backend=record.queue_backend,
            queue_name=record.queue_name,
            queue_job_id=record.queue_job_id,
            enqueued_at=record.enqueued_at,
            attempt_count=record.attempt_count,
            max_attempts=record.max_attempts,
            next_run_at=record.next_run_at,
            cancel_requested_at=record.cancel_requested_at,
            worker_id=record.worker_id,
            heartbeat_at=record.heartbeat_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


def _requeue_summary(result: RequeueAIJobsResult) -> dict[str, object]:
    return {
        "scanned": result.scanned,
        "enqueued": result.enqueued,
        "failed": result.failed,
        "job_ids": [str(job_id) for job_id in result.job_ids],
    }


def _application_error(exc: Exception) -> ApplicationError:
    if isinstance(exc, ApplicationError):
        return exc
    return ApplicationError(
        code=ErrorCode.INTERNAL_ERROR,
        message="admin AI job action failed",
        details={"error": redact_sensitive_text(str(exc))},
    )


def _commit_if_supported(session: Session) -> None:
    commit = getattr(session, "commit", None)
    if callable(commit):
        commit()


def _rollback_if_supported(session: Session) -> None:
    rollback = getattr(session, "rollback", None)
    if callable(rollback):
        rollback()
