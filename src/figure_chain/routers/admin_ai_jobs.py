from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from figure_chain.access import OperationContext
from figure_chain.dependencies import (
    get_admin_ai_jobs_service,
    require_operator_context,
)
from figure_chain.schemas import (
    AdminAIJobActionRequest,
    AdminAIJobActionResponse,
    AdminAIJobListResponse,
    AdminAIJobsRequeueRequest,
    AiJobEventListResponse,
    AiJobHealthResponse,
    AiJobResponse,
)
from figure_chain.services.admin_ai_jobs import AdminAIJobsService

router = APIRouter(prefix="/api/v1/admin/ai", tags=["admin"])


@router.get("/health", response_model=AiJobHealthResponse)
def get_admin_ai_job_health(
    service: Annotated[AdminAIJobsService, Depends(get_admin_ai_jobs_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AiJobHealthResponse:
    return service.get_health()


@router.get("/jobs", response_model=AdminAIJobListResponse)
def list_admin_ai_jobs(
    service: Annotated[AdminAIJobsService, Depends(get_admin_ai_jobs_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
    status: str | None = None,
    target_kind: str | None = None,
    target_id: int | None = Query(default=None, ge=1),
    queue_backend: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminAIJobListResponse:
    return service.list_jobs(
        status=status,
        target_kind=target_kind,
        target_id=target_id,
        queue_backend=queue_backend,
        limit=limit,
        offset=offset,
    )


@router.post("/jobs/requeue", response_model=AdminAIJobActionResponse)
def requeue_admin_ai_jobs(
    request: AdminAIJobsRequeueRequest,
    service: Annotated[AdminAIJobsService, Depends(get_admin_ai_jobs_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminAIJobActionResponse:
    return service.requeue_jobs(request)


@router.get("/jobs/{job_id}", response_model=AiJobResponse)
def get_admin_ai_job(
    job_id: UUID,
    service: Annotated[AdminAIJobsService, Depends(get_admin_ai_jobs_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AiJobResponse:
    return service.get_job(job_id)


@router.get("/jobs/{job_id}/events", response_model=AiJobEventListResponse)
def list_admin_ai_job_events(
    job_id: UUID,
    service: Annotated[AdminAIJobsService, Depends(get_admin_ai_jobs_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AiJobEventListResponse:
    return service.list_job_events(job_id)


@router.post("/jobs/{job_id}/cancel", response_model=AdminAIJobActionResponse)
def cancel_admin_ai_job(
    job_id: UUID,
    request: AdminAIJobActionRequest,
    service: Annotated[AdminAIJobsService, Depends(get_admin_ai_jobs_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminAIJobActionResponse:
    return service.cancel_job(job_id, request)


@router.post("/jobs/{job_id}/retry", response_model=AdminAIJobActionResponse)
def retry_admin_ai_job(
    job_id: UUID,
    request: AdminAIJobActionRequest,
    service: Annotated[AdminAIJobsService, Depends(get_admin_ai_jobs_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminAIJobActionResponse:
    return service.retry_job(job_id, request)
