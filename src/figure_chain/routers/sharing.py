from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from figure_chain.dependencies import get_sharing_service
from figure_chain.schemas import (
    ChainShareCreateRequest,
    ChainShareCreateResponse,
    ChainShareDetailResponse,
    MarkdownExportRequest,
    MarkdownExportResponse,
)
from figure_chain.services.sharing import SharingService

router = APIRouter(prefix="/api/v1/chains", tags=["sharing"])


@router.post("/share", response_model=ChainShareCreateResponse)
def create_share(
    request: ChainShareCreateRequest,
    service: Annotated[SharingService, Depends(get_sharing_service)],
) -> ChainShareCreateResponse:
    return service.create_share(request)


@router.get("/share/{share_slug}", response_model=ChainShareDetailResponse)
def get_share(
    share_slug: str,
    service: Annotated[SharingService, Depends(get_sharing_service)],
) -> ChainShareDetailResponse:
    return service.get_share(share_slug)


@router.post("/export/markdown", response_model=MarkdownExportResponse)
def export_markdown(
    request: MarkdownExportRequest,
    service: Annotated[SharingService, Depends(get_sharing_service)],
) -> MarkdownExportResponse:
    return service.export_markdown(request)
