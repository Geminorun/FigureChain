from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_people_service, get_sharing_service, get_source_service
from figure_chain.schemas import (
    ChainShareCreateRequest,
    ChainShareCreateResponse,
    LinkedEncounterEvidenceResponse,
    MarkdownExportRequest,
    MarkdownExportResponse,
    PersonAliasResponse,
    PersonDetailResponse,
    PersonEncounterListItemResponse,
    PersonEncounterListResponse,
    PersonEncounterSummaryCountsResponse,
    PersonExternalIdResponse,
    SourceRefDetailResponse,
    SourceWorkDetailResponse,
)
from figure_data.people.detail import PersonEncounterFilters

SOURCE_PERSON_ID = UUID("38966b03-8aa7-5143-8021-2d266889b6c5")
TARGET_PERSON_ID = UUID("46cfdf66-08c4-5876-964b-4a95d098afe9")
ENCOUNTER_ID = UUID("e4f22ec2-22f7-4cda-bcc1-73aa83d0685f")
SHARE_ID = UUID("00000000-0000-0000-0000-0000000005c0")


class Stage5CPeopleService:
    def search(self, query: str, limit: int) -> object:
        raise AssertionError("search should not be called by contract smoke")

    def get_detail(self, person_id: UUID) -> PersonDetailResponse:
        return PersonDetailResponse(
            person_id=person_id,
            display_name="許幾",
            primary_name_zh_hant="許幾",
            primary_name_zh_hans="许几",
            primary_name_romanized="Xu Ji",
            birth_year=None,
            death_year=None,
            index_year=1044,
            floruit_start_year=None,
            floruit_end_year=None,
            dynasty_code=15,
            dynasty_label_zh="宋",
            dynasty_label_en="Song",
            is_female=False,
            notes="Stage 5C contract fixture",
            aliases=[
                PersonAliasResponse(
                    alias_zh_hant="許幾",
                    alias_zh_hans="许几",
                    alias_romanized="Xu Ji",
                    alias_type_label_zh="姓名",
                    alias_type_label_en="name",
                )
            ],
            external_ids=[PersonExternalIdResponse(source_name="CBDB", external_id="780")],
            encounter_summary=PersonEncounterSummaryCountsResponse(
                active_count=1,
                path_eligible_count=1,
                high_certainty_count=1,
            ),
        )

    def list_encounters(
        self,
        person_id: UUID,
        filters: PersonEncounterFilters,
    ) -> PersonEncounterListResponse:
        return PersonEncounterListResponse(
            items=[
                PersonEncounterListItemResponse(
                    encounter_id=ENCOUNTER_ID,
                    other_person_id=TARGET_PERSON_ID,
                    other_person_name="韓琦",
                    other_person_birth_year=1008,
                    other_person_death_year=1075,
                    encounter_kind="direct_interaction",
                    certainty_level="high",
                    path_eligible=True,
                    source_work_id=7596,
                    source_title="宋人傳記資料索引",
                    pages="3853784",
                    evidence_summary="許幾與韓琦存在已審核直接交往證據",
                    status="active",
                    reviewed_by="acceptance",
                    reviewed_at=datetime(2026, 6, 19, tzinfo=UTC),
                )
            ],
            count=1,
            limit=filters.limit,
            offset=filters.offset,
        )


class Stage5CSourceService:
    def get_source_work(self, source_work_id: int) -> SourceWorkDetailResponse:
        return SourceWorkDetailResponse(
            source_work_id=source_work_id,
            text_code=7596,
            title_zh="宋人傳記資料索引",
            title_en="Index to Song Biographical Materials",
            source_name="CBDB",
            source_table="TEXT_CODES",
            source_pk=str(source_work_id),
            ref_count=12,
            encounter_count=1,
        )

    def get_source_ref(self, source_ref_id: int) -> SourceRefDetailResponse:
        return SourceRefDetailResponse(
            source_ref_id=source_ref_id,
            source_work=self.get_source_work(7596),
            ref_source_table="BIOG_MAIN",
            ref_source_pk="780",
            pages="3853784",
            notes="Stage 5C source ref fixture",
            source_name="CBDB",
            source_table="BIOG_SOURCE_DATA",
            source_pk=str(source_ref_id),
            linked_encounter_evidence=[
                LinkedEncounterEvidenceResponse(
                    evidence_id=3853784,
                    encounter_id=ENCOUNTER_ID,
                    evidence_kind="reviewed",
                    evidence_summary="許幾與韓琦存在已審核直接交往證據",
                    pages="3853784",
                    created_at=datetime(2026, 6, 19, tzinfo=UTC),
                )
            ],
        )


class Stage5CSharingService:
    def create_share(self, request: ChainShareCreateRequest) -> ChainShareCreateResponse:
        assert request.source_person_id == SOURCE_PERSON_ID
        assert request.target_person_id == TARGET_PERSON_ID
        return ChainShareCreateResponse(
            share_slug="stage5c-smoke",
            url_path="/share/stage5c-smoke",
        )

    def get_share(self, share_slug: str) -> object:
        raise AssertionError("get_share should not be called by contract smoke")

    def export_markdown(self, request: MarkdownExportRequest) -> MarkdownExportResponse:
        assert request.share_slug == "stage5c-smoke"
        return MarkdownExportResponse(
            content="# FigureChain 人物链\n\n- 許幾 -> 韓琦\n",
            filename="figurechain-stage5c-smoke.md",
            source_ids={
                "encounter_ids": [str(ENCOUNTER_ID)],
                "source_ref_ids": ["3853784"],
                "source_work_ids": ["7596"],
                "ai_run_ids": [],
                "retrieval_document_ids": [],
            },
        )


def app_client() -> TestClient:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_people_service] = lambda: Stage5CPeopleService()
    app.dependency_overrides[get_source_service] = lambda: Stage5CSourceService()
    app.dependency_overrides[get_sharing_service] = lambda: Stage5CSharingService()
    return TestClient(app)


def test_stage5c_people_source_and_sharing_contracts() -> None:
    with app_client() as client:
        person_response = client.get(f"/api/v1/people/{SOURCE_PERSON_ID}")
        encounters_response = client.get(
            f"/api/v1/people/{SOURCE_PERSON_ID}/encounters",
            params={"limit": 10, "offset": 0},
        )
        source_work_response = client.get("/api/v1/source-works/7596")
        source_ref_response = client.get("/api/v1/source-refs/3853784")
        share_response = client.post(
            "/api/v1/chains/share",
            json={
                "source_person_id": str(SOURCE_PERSON_ID),
                "target_person_id": str(TARGET_PERSON_ID),
                "chain_hash": "stage5c-chain-hash",
                "path_payload": {
                    "people": [
                        {"person_id": str(SOURCE_PERSON_ID), "display_name": "許幾"},
                        {"person_id": str(TARGET_PERSON_ID), "display_name": "韓琦"},
                    ],
                    "edges": [{"encounter_id": str(ENCOUNTER_ID)}],
                },
                "filters_applied": {"max_depth": 6},
            },
        )
        export_response = client.post(
            "/api/v1/chains/export/markdown",
            json={"share_slug": "stage5c-smoke", "format": "markdown"},
        )

    assert person_response.status_code == 200
    person = person_response.json()
    assert person["aliases"][0]["alias_zh_hant"] == "許幾"
    assert person["external_ids"] == [{"source_name": "CBDB", "external_id": "780"}]
    assert person["encounter_summary"]["path_eligible_count"] == 1

    assert encounters_response.status_code == 200
    encounters = encounters_response.json()
    assert encounters["limit"] == 10
    assert encounters["offset"] == 0
    assert encounters["items"][0]["encounter_id"] == str(ENCOUNTER_ID)
    assert encounters["items"][0]["source_work_id"] == 7596

    assert source_work_response.status_code == 200
    source_work = source_work_response.json()
    assert source_work["ref_count"] == 12
    assert source_work["encounter_count"] == 1

    assert source_ref_response.status_code == 200
    source_ref = source_ref_response.json()
    assert source_ref["source_work"]["source_work_id"] == 7596
    assert source_ref["linked_encounter_evidence"][0]["evidence_id"] == 3853784
    assert source_ref["linked_encounter_evidence"][0]["encounter_id"] == str(ENCOUNTER_ID)

    assert share_response.status_code == 200
    share = share_response.json()
    assert share["share_slug"] == "stage5c-smoke"
    assert share["url_path"] == "/share/stage5c-smoke"

    assert export_response.status_code == 200
    export = export_response.json()
    assert export["filename"] == "figurechain-stage5c-smoke.md"
    assert export["content"].startswith("# FigureChain 人物链")
    assert export["source_ids"]["encounter_ids"] == [str(ENCOUNTER_ID)]
    assert export["source_ids"]["source_ref_ids"] == ["3853784"]
