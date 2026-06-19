from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_people_service
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    PersonAliasResponse,
    PersonDetailResponse,
    PersonEncounterListItemResponse,
    PersonEncounterListResponse,
    PersonEncounterSummaryCountsResponse,
    PersonExternalIdResponse,
)
from figure_data.people.detail import PersonEncounterFilters

PERSON_ID = UUID("00000000-0000-0000-0000-000000000001")


class FakePeopleService:
    def __init__(self) -> None:
        self.filters: PersonEncounterFilters | None = None

    def search(self, query: str, limit: int) -> object:
        raise AssertionError("search should not be called")

    def get_detail(self, person_id: UUID) -> PersonDetailResponse:
        if person_id != PERSON_ID:
            raise ApplicationError(
                code=ErrorCode.PERSON_NOT_FOUND,
                message="person was not found",
                details={"person_id": str(person_id)},
            )
        return PersonDetailResponse(
            person_id=PERSON_ID,
            display_name="諸葛亮",
            primary_name_zh_hant="諸葛亮",
            primary_name_zh_hans="诸葛亮",
            primary_name_romanized="Zhuge Liang",
            birth_year=181,
            death_year=234,
            index_year=207,
            floruit_start_year=None,
            floruit_end_year=None,
            dynasty_code=6,
            dynasty_label_zh="三國",
            dynasty_label_en="Three Kingdoms",
            is_female=False,
            notes="蜀漢丞相",
            aliases=[
                PersonAliasResponse(
                    alias_zh_hant="孔明",
                    alias_zh_hans="孔明",
                    alias_romanized=None,
                    alias_type_label_zh="字",
                    alias_type_label_en="courtesy name",
                )
            ],
            external_ids=[PersonExternalIdResponse(source_name="CBDB", external_id="25403")],
            encounter_summary=PersonEncounterSummaryCountsResponse(
                active_count=2,
                path_eligible_count=1,
                high_certainty_count=1,
            ),
        )

    def list_encounters(
        self,
        person_id: UUID,
        filters: PersonEncounterFilters,
    ) -> PersonEncounterListResponse:
        self.filters = filters
        return PersonEncounterListResponse(
            items=[
                PersonEncounterListItemResponse(
                    encounter_id=UUID("00000000-0000-0000-0000-000000000101"),
                    other_person_id=UUID("00000000-0000-0000-0000-000000000002"),
                    other_person_name="司馬懿",
                    other_person_birth_year=179,
                    other_person_death_year=251,
                    encounter_kind="direct_interaction",
                    certainty_level="high",
                    path_eligible=True,
                    source_work_id=1,
                    source_title="三國志",
                    pages="12a",
                    evidence_summary="有直接交往證據",
                    status="active",
                    reviewed_by="lyl",
                    reviewed_at=datetime(2026, 6, 19, tzinfo=UTC),
                )
            ],
            count=1,
            limit=filters.limit,
            offset=filters.offset,
        )


def test_person_detail_route_returns_payload() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_people_service] = lambda: FakePeopleService()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/people/{PERSON_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["person_id"] == str(PERSON_ID)
    assert body["display_name"] == "諸葛亮"
    assert body["aliases"][0]["alias_zh_hant"] == "孔明"
    assert body["encounter_summary"]["path_eligible_count"] == 1


def test_person_encounters_route_passes_filters() -> None:
    service = FakePeopleService()
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_people_service] = lambda: service

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/people/{PERSON_ID}/encounters",
            params={
                "status": "active",
                "path_eligible": "true",
                "certainty_level": "high",
                "encounter_kind": "direct_interaction",
                "limit": 10,
                "offset": 20,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["other_person_name"] == "司馬懿"
    assert service.filters == PersonEncounterFilters(
        status="active",
        path_eligible=True,
        certainty_level="high",
        encounter_kind="direct_interaction",
        limit=10,
        offset=20,
    )


def test_person_detail_route_returns_404_when_missing() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_people_service] = lambda: FakePeopleService()

    with TestClient(app) as client:
        response = client.get("/api/v1/people/00000000-0000-0000-0000-000000000999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "person_not_found"
