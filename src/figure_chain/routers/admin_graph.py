from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from figure_chain.access import OperationContext
from figure_chain.dependencies import (
    get_admin_graph_service,
    require_operator_context,
)
from figure_chain.schemas import (
    AdminGraphOperationRequest,
    AdminGraphOperationResponse,
    AdminGraphStatusResponse,
    AdminGraphSyncRequest,
)
from figure_chain.services.admin_graph import AdminGraphService

router = APIRouter(prefix="/api/v1/admin/graph", tags=["admin"])


@router.get("/status", response_model=AdminGraphStatusResponse)
def get_admin_graph_status(
    service: Annotated[AdminGraphService, Depends(get_admin_graph_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminGraphStatusResponse:
    return service.get_status()


@router.post("/validate-encounters", response_model=AdminGraphOperationResponse)
def validate_admin_encounters(
    request: AdminGraphOperationRequest,
    service: Annotated[AdminGraphService, Depends(get_admin_graph_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminGraphOperationResponse:
    return service.start_validate_encounters(request)


@router.post("/sync", response_model=AdminGraphOperationResponse)
def sync_admin_graph(
    request: AdminGraphSyncRequest,
    service: Annotated[AdminGraphService, Depends(get_admin_graph_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminGraphOperationResponse:
    return service.start_sync_graph(request)


@router.post("/validate-graph", response_model=AdminGraphOperationResponse)
def validate_admin_graph(
    request: AdminGraphOperationRequest,
    service: Annotated[AdminGraphService, Depends(get_admin_graph_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminGraphOperationResponse:
    return service.start_validate_graph(request)
