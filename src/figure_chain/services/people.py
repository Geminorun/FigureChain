from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from figure_chain.schemas import PeopleSearchResponse, PersonSearchItem, display_name
from figure_data.search.person_search import PersonSearchResult, search_people

SearchPeopleFn = Callable[[Session, str, int], list[PersonSearchResult]]


class PeopleService:
    def __init__(
        self,
        session: Session,
        search_fn: SearchPeopleFn = search_people,
    ) -> None:
        self._session = session
        self._search_fn = search_fn

    def search(self, query: str, limit: int) -> PeopleSearchResponse:
        normalized_query = query.strip()
        results = self._search_fn(self._session, normalized_query, limit)
        return PeopleSearchResponse(
            query=normalized_query,
            limit=limit,
            items=[self._to_item(result) for result in results],
        )

    def _to_item(self, result: PersonSearchResult) -> PersonSearchItem:
        return PersonSearchItem(
            person_id=result.person_id,
            display_name=display_name(
                result.primary_name_zh_hant,
                result.primary_name_zh_hans,
                result.primary_name_romanized,
                result.person_id,
            ),
            primary_name_zh_hant=result.primary_name_zh_hant,
            primary_name_zh_hans=result.primary_name_zh_hans,
            primary_name_romanized=result.primary_name_romanized,
            birth_year=result.birth_year,
            death_year=result.death_year,
            index_year=result.index_year,
            dynasty_code=result.dynasty_code,
            matching_aliases=result.matching_aliases,
            external_ids=result.external_ids,
        )
