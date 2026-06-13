from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from figure_chain.dependencies import get_ai_service
from figure_chain.schemas import AIChainExplanationResponse, AIRunResponse
from figure_chain.services.ai import AIService

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get("/chains/explanations/{chain_hash}", response_model=AIChainExplanationResponse)
def chain_explanation(
    chain_hash: str,
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AIChainExplanationResponse:
    return service.get_chain_explanation(chain_hash)


@router.get("/runs/{run_id}", response_model=AIRunResponse)
def ai_run(
    run_id: UUID,
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AIRunResponse:
    return service.get_ai_run(run_id)
