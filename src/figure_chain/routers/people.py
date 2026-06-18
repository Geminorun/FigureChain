from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from figure_chain.dependencies import get_people_service
from figure_chain.schemas import (
    PeopleSearchResponse,
    PersonDetailResponse,
    PersonEncounterListResponse,
)
from figure_chain.services.people import PeopleService
from figure_data.people.detail import PersonEncounterFilters

router = APIRouter(prefix="/api/v1/people", tags=["people"])


@router.get("/search", response_model=PeopleSearchResponse)
def search_people_endpoint(
    q: Annotated[str, Query(min_length=1)],
    service: Annotated[PeopleService, Depends(get_people_service)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> PeopleSearchResponse:
    return service.search(q, limit)


@router.get("/{person_id}/encounters", response_model=PersonEncounterListResponse)
def person_encounters(
    person_id: UUID,
    service: Annotated[PeopleService, Depends(get_people_service)],
    status: str | None = "active",
    path_eligible: bool | None = None,
    certainty_level: str | None = None,
    encounter_kind: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PersonEncounterListResponse:
    return service.list_encounters(
        person_id,
        PersonEncounterFilters(
            status=status,
            path_eligible=path_eligible,
            certainty_level=certainty_level,
            encounter_kind=encounter_kind,
            limit=limit,
            offset=offset,
        ),
    )


@router.get("/{person_id}", response_model=PersonDetailResponse)
def person_detail(
    person_id: UUID,
    service: Annotated[PeopleService, Depends(get_people_service)],
) -> PersonDetailResponse:
    return service.get_detail(person_id)
