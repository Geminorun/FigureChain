from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from figure_chain.dependencies import get_health_service
from figure_chain.schemas import ReadyResponse
from figure_chain.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {
        "status": "alive",
        "service": "figure-chain-api",
    }


@router.get("/health/ready", response_model=ReadyResponse)
def ready(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> ReadyResponse | JSONResponse:
    response = service.readiness()
    if response.status == "not_ready":
        return JSONResponse(status_code=503, content=response.model_dump())
    return response
