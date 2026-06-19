from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from figure_chain.dependencies import get_system_service, require_operator_context
from figure_chain.schemas import SystemDiagnosticsResponse
from figure_chain.services.system import SystemService

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/diagnostics", response_model=SystemDiagnosticsResponse)
def diagnostics(
    _context: Annotated[object, Depends(require_operator_context)],
    service: Annotated[SystemService, Depends(get_system_service)],
) -> SystemDiagnosticsResponse:
    return service.diagnostics()
