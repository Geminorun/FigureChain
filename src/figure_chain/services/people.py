from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    PeopleSearchResponse,
    PersonAliasResponse,
    PersonDetailResponse,
    PersonEncounterListItemResponse,
    PersonEncounterListResponse,
    PersonEncounterSummaryCountsResponse,
    PersonExternalIdResponse,
    PersonSearchItem,
    display_name,
)
from figure_data.people.detail import (
    PersonDetailNotFoundError,
    PersonEncounterFilters,
    get_person_detail,
    list_person_encounters,
)
from figure_data.people.types import PersonDetail, PersonEncounterItem
from figure_data.search.person_search import PersonSearchResult, search_people

SearchPeopleFn = Callable[[Session, str, int], list[PersonSearchResult]]
GetPersonDetailFn = Callable[[Session, UUID], PersonDetail]
ListPersonEncountersFn = Callable[
    [Session, UUID, PersonEncounterFilters],
    list[PersonEncounterItem],
]


class PeopleService:
    def __init__(
        self,
        session: Session,
        search_fn: SearchPeopleFn = search_people,
        get_person_detail_fn: GetPersonDetailFn = get_person_detail,
        list_person_encounters_fn: ListPersonEncountersFn = list_person_encounters,
    ) -> None:
        self._session = session
        self._search_fn = search_fn
        self._get_person_detail_fn = get_person_detail_fn
        self._list_person_encounters_fn = list_person_encounters_fn

    def search(self, query: str, limit: int) -> PeopleSearchResponse:
        normalized_query = query.strip()
        results = self._search_fn(self._session, normalized_query, limit)
        return PeopleSearchResponse(
            query=normalized_query,
            limit=limit,
            items=[self._to_item(result) for result in results],
        )

    def get_detail(self, person_id: UUID) -> PersonDetailResponse:
        try:
            detail = self._get_person_detail_fn(self._session, person_id)
        except PersonDetailNotFoundError as exc:
            raise ApplicationError(
                code=ErrorCode.PERSON_NOT_FOUND,
                message="person was not found",
                details={"person_id": str(person_id)},
            ) from exc
        return self._detail(detail)

    def list_encounters(
        self,
        person_id: UUID,
        filters: PersonEncounterFilters,
    ) -> PersonEncounterListResponse:
        items = self._list_person_encounters_fn(self._session, person_id, filters)
        return PersonEncounterListResponse(
            items=[self._encounter_item(item) for item in items],
            count=len(items),
            limit=filters.limit,
            offset=filters.offset,
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

    def _detail(self, detail: PersonDetail) -> PersonDetailResponse:
        person_id = str(detail.person_id)
        return PersonDetailResponse(
            person_id=detail.person_id,
            display_name=display_name(
                detail.primary_name_zh_hant,
                detail.primary_name_zh_hans,
                detail.primary_name_romanized,
                person_id,
            ),
            primary_name_zh_hant=detail.primary_name_zh_hant,
            primary_name_zh_hans=detail.primary_name_zh_hans,
            primary_name_romanized=detail.primary_name_romanized,
            birth_year=detail.birth_year,
            death_year=detail.death_year,
            index_year=detail.index_year,
            floruit_start_year=detail.floruit_start_year,
            floruit_end_year=detail.floruit_end_year,
            dynasty_code=detail.dynasty_code,
            dynasty_label_zh=detail.dynasty_label_zh,
            dynasty_label_en=detail.dynasty_label_en,
            is_female=detail.is_female,
            notes=detail.notes,
            aliases=[
                PersonAliasResponse(
                    alias_zh_hant=alias.alias_zh_hant,
                    alias_zh_hans=alias.alias_zh_hans,
                    alias_romanized=alias.alias_romanized,
                    alias_type_label_zh=alias.alias_type_label_zh,
                    alias_type_label_en=alias.alias_type_label_en,
                )
                for alias in detail.aliases
            ],
            external_ids=[
                PersonExternalIdResponse(
                    source_name=external_id.source_name,
                    external_id=external_id.external_id,
                )
                for external_id in detail.external_ids
            ],
            encounter_summary=PersonEncounterSummaryCountsResponse(
                active_count=detail.encounter_summary.active_count,
                path_eligible_count=detail.encounter_summary.path_eligible_count,
                high_certainty_count=detail.encounter_summary.high_certainty_count,
            ),
        )

    def _encounter_item(self, item: PersonEncounterItem) -> PersonEncounterListItemResponse:
        return PersonEncounterListItemResponse(
            encounter_id=item.encounter_id,
            other_person_id=item.other_person_id,
            other_person_name=item.other_person_name,
            other_person_birth_year=item.other_person_birth_year,
            other_person_death_year=item.other_person_death_year,
            encounter_kind=item.encounter_kind,
            certainty_level=item.certainty_level,
            path_eligible=item.path_eligible,
            source_work_id=item.source_work_id,
            source_title=item.source_title,
            pages=item.pages,
            evidence_summary=item.evidence_summary,
            status=item.status,
            reviewed_by=item.reviewed_by,
            reviewed_at=item.reviewed_at,
        )
