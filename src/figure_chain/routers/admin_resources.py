from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from figure_chain.access import OperationContext
from figure_chain.dependencies import (
    get_admin_resources_service,
    require_operator_context,
)
from figure_chain.schemas import (
    AdminResourceListResponse,
    AdminResourceQueryRequest,
    AdminResourceQueryResponse,
)
from figure_chain.services.admin_resources import AdminResourcesService

router = APIRouter(prefix="/api/v1/admin/resources", tags=["admin"])


@router.get("", response_model=AdminResourceListResponse)
def list_admin_resources(
    service: Annotated[AdminResourcesService, Depends(get_admin_resources_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminResourceListResponse:
    return service.list_resources()


@router.post("/query", response_model=AdminResourceQueryResponse)
def query_admin_resource(
    request: AdminResourceQueryRequest,
    service: Annotated[AdminResourcesService, Depends(get_admin_resources_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminResourceQueryResponse:
    return service.query_resource(request)
