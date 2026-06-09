from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_encounter_service
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    EncounterDetailResponse,
    EncounterEvidenceResponse,
    EncounterPersonResponse,
    SourceRefResponse,
)

ENCOUNTER_ID = UUID("e4f22ec2-22f7-4cda-bcc1-73aa83d0685f")


class FakeEncounterService:
    def get_detail(self, encounter_id: UUID) -> EncounterDetailResponse:
        if encounter_id != ENCOUNTER_ID:
            raise ApplicationError(
                code=ErrorCode.ENCOUNTER_NOT_FOUND,
                message="encounter was not found",
                details={"encounter_id": str(encounter_id)},
            )
        now = datetime(2026, 6, 9, tzinfo=UTC)
        return EncounterDetailResponse(
            encounter_id=ENCOUNTER_ID,
            status="active",
            encounter_kind="direct_interaction",
            certainty_level="high",
            path_eligible=True,
            source_work_id=7596,
            pages="11905",
            evidence_summary="许几谒韩琦于魏",
            review_note=None,
            reviewed_by="lyl",
            reviewed_at=now,
            person_a=EncounterPersonResponse(
                person_id="person-a",
                cbdb_id=780,
                display_name="許幾",
                primary_name_zh_hant="許幾",
                primary_name_zh_hans="许几",
                primary_name_romanized="Xu Ji",
                birth_year=1054,
                death_year=1115,
                external_ids=["780"],
            ),
            person_b=EncounterPersonResponse(
                person_id="person-b",
                cbdb_id=630,
                display_name="韓琦",
                primary_name_zh_hant="韓琦",
                primary_name_zh_hans="韩琦",
                primary_name_romanized="Han Qi",
                birth_year=1008,
                death_year=1075,
                external_ids=["630"],
            ),
            evidence=[
                EncounterEvidenceResponse(
                    evidence_id=12,
                    candidate_table="relationship_candidates",
                    candidate_id=960664,
                    source_ref_id=3853784,
                    source_work_id=7596,
                    pages="11905",
                    evidence_kind="candidate",
                    evidence_summary="许几谒韩琦于魏",
                    created_at=now,
                )
            ],
            source_refs=[
                SourceRefResponse(
                    source_ref_id=3853784,
                    source_work_id=7596,
                    title_zh=None,
                    title_en=None,
                    pages="11905",
                    notes="字先之 貴溪人 以諸生謁韓琦於魏",
                )
            ],
        )


def test_encounter_detail_returns_evidence() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_encounter_service] = lambda: FakeEncounterService()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/encounters/{ENCOUNTER_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["encounter_id"] == str(ENCOUNTER_ID)
    assert body["evidence"][0]["candidate_id"] == 960664
    assert body["source_refs"][0]["pages"] == "11905"


def test_encounter_detail_returns_404_when_missing() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_encounter_service] = lambda: FakeEncounterService()

    with TestClient(app) as client:
        response = client.get("/api/v1/encounters/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "encounter_not_found"
