from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from figure_chain.dependencies import get_people_service
from figure_chain.schemas import PeopleSearchResponse
from figure_chain.services.people import PeopleService

router = APIRouter(prefix="/api/v1/people", tags=["people"])


@router.get("/search", response_model=PeopleSearchResponse)
def search_people_endpoint(
    q: Annotated[str, Query(min_length=1)],
    service: Annotated[PeopleService, Depends(get_people_service)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> PeopleSearchResponse:
    return service.search(q, limit)
