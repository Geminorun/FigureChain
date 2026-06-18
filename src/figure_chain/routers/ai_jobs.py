from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from figure_chain.dependencies import get_ai_jobs_service
from figure_chain.schemas import AiJobCreateRequest, AiJobListResponse, AiJobResponse
from figure_chain.services.ai_jobs import AIJobsService

router = APIRouter(prefix="/api/v1/ai/jobs", tags=["ai-jobs"])


@router.post("", response_model=AiJobResponse)
def create_ai_job(
    request: AiJobCreateRequest,
    service: Annotated[AIJobsService, Depends(get_ai_jobs_service)],
) -> AiJobResponse:
    return service.create_job(request)


@router.get("/{job_id}", response_model=AiJobResponse)
def get_ai_job(
    job_id: UUID,
    service: Annotated[AIJobsService, Depends(get_ai_jobs_service)],
) -> AiJobResponse:
    return service.get_job(job_id)


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
