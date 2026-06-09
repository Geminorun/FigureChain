from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from figure_chain.dependencies import get_encounter_service
from figure_chain.schemas import EncounterDetailResponse
from figure_chain.services.encounters import EncounterService

router = APIRouter(prefix="/api/v1/encounters", tags=["encounters"])


@router.get("/{encounter_id}", response_model=EncounterDetailResponse)
def encounter_detail(
    encounter_id: UUID,
    service: Annotated[EncounterService, Depends(get_encounter_service)],
) -> EncounterDetailResponse:
    return service.get_detail(encounter_id)
