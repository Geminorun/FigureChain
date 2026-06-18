from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from figure_chain.dependencies import get_source_service
from figure_chain.schemas import SourceRefDetailResponse, SourceWorkDetailResponse
from figure_chain.services.sources import SourceService

router = APIRouter(tags=["sources"])


@router.get("/api/v1/source-works/{source_work_id}", response_model=SourceWorkDetailResponse)
def source_work_detail(
    source_work_id: int,
    service: Annotated[SourceService, Depends(get_source_service)],
) -> SourceWorkDetailResponse:
    return service.get_source_work(source_work_id)


@router.get("/api/v1/source-refs/{source_ref_id}", response_model=SourceRefDetailResponse)
def source_ref_detail(
    source_ref_id: int,
    service: Annotated[SourceService, Depends(get_source_service)],
) -> SourceRefDetailResponse:
    return service.get_source_ref(source_ref_id)
