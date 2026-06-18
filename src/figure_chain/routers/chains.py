from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from figure_chain.dependencies import get_chain_service
from figure_chain.schemas import (
    MultiPathChainRequest,
    MultiPathChainResponse,
    ShortestChainRequest,
    ShortestChainResponse,
)
from figure_chain.services.chains import ChainService

router = APIRouter(prefix="/api/v1/chains", tags=["chains"])


@router.post("/shortest", response_model=ShortestChainResponse)
def shortest_chain(
    request: ShortestChainRequest,
    service: Annotated[ChainService, Depends(get_chain_service)],
) -> ShortestChainResponse:
    return service.shortest(request)


@router.post("/multipath", response_model=MultiPathChainResponse)
def multipath_chain(
    request: MultiPathChainRequest,
    service: Annotated[ChainService, Depends(get_chain_service)],
) -> MultiPathChainResponse:
    return service.multipath(request)
