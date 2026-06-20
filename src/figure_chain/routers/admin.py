from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from figure_chain.dependencies import get_admin_service, require_operator_context
from figure_chain.schemas import AdminOperationDetailResponse, AdminOperationListResponse
from figure_chain.services.admin import AdminOperationFilters, AdminService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/operations", response_model=AdminOperationListResponse)
def list_admin_operations_endpoint(
    _context: Annotated[object, Depends(require_operator_context)],
    service: Annotated[AdminService, Depends(get_admin_service)],
    status: str | None = None,
    operation_type: str | None = None,
    actor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AdminOperationListResponse:
    return service.list_operations(
        AdminOperationFilters(
            status=status,
            operation_type=operation_type,
            actor=actor,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/operations/{operation_id}", response_model=AdminOperationDetailResponse)
def get_admin_operation_endpoint(
    operation_id: UUID,
    _context: Annotated[object, Depends(require_operator_context)],
    service: Annotated[AdminService, Depends(get_admin_service)],
) -> AdminOperationDetailResponse:
    return service.get_operation(operation_id)
