from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from figure_chain.dependencies import get_ai_jobs_service, require_reviewer_context
from figure_chain.schemas import (
    AiJobCancelRequest,
    AiJobCreateRequest,
    AiJobEventListResponse,
    AiJobHealthResponse,
    AiJobListResponse,
    AiJobResponse,
    AiJobRetryRequest,
)
from figure_chain.services.ai_jobs import AIJobsService

router = APIRouter(prefix="/api/v1/ai/jobs", tags=["ai-jobs"])
health_router = APIRouter(prefix="/api/v1/ai", tags=["ai-jobs"])


@router.post("", response_model=AiJobResponse)
def create_ai_job(
    request: AiJobCreateRequest,
    _context: Annotated[object, Depends(require_reviewer_context)],
    service: Annotated[AIJobsService, Depends(get_ai_jobs_service)],
) -> AiJobResponse:
    return service.create_job(request)


@router.get("/{job_id}", response_model=AiJobResponse)
def get_ai_job(
    job_id: UUID,
    service: Annotated[AIJobsService, Depends(get_ai_jobs_service)],
) -> AiJobResponse:
    return service.get_job(job_id)


@router.get("/{job_id}/events", response_model=AiJobEventListResponse)
def list_ai_job_events(
    job_id: UUID,
    service: Annotated[AIJobsService, Depends(get_ai_jobs_service)],
) -> AiJobEventListResponse:
    return service.list_job_events(job_id)


@router.post("/{job_id}/cancel", response_model=AiJobResponse)
def cancel_ai_job(
    job_id: UUID,
    request: AiJobCancelRequest,
    _context: Annotated[object, Depends(require_reviewer_context)],
    service: Annotated[AIJobsService, Depends(get_ai_jobs_service)],
) -> AiJobResponse:
    return service.cancel_job(job_id, cancelled_by=request.cancelled_by)


@router.post("/{job_id}/retry", response_model=AiJobResponse)
def retry_ai_job(
    job_id: UUID,
    request: AiJobRetryRequest,
    _context: Annotated[object, Depends(require_reviewer_context)],
    service: Annotated[AIJobsService, Depends(get_ai_jobs_service)],
) -> AiJobResponse:
    return service.retry_job(job_id, created_by=request.created_by)


@router.get("", response_model=AiJobListResponse)
def list_ai_jobs(
    service: Annotated[AIJobsService, Depends(get_ai_jobs_service)],
    target_type: str,
    target_kind: str,
    target_id: int = Query(ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> AiJobListResponse:
    return service.list_jobs(
        target_type=target_type,
        target_kind=target_kind,
        target_id=target_id,
        limit=limit,
    )


@health_router.get("/health", response_model=AiJobHealthResponse)
def get_ai_job_health(
    service: Annotated[AIJobsService, Depends(get_ai_jobs_service)],
    stale_after_seconds: int = Query(default=300, ge=1, le=86400),
) -> AiJobHealthResponse:
    return service.get_queue_health(stale_after_seconds=stale_after_seconds)
