from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_source_service
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    LinkedEncounterEvidenceResponse,
    SourceRefDetailResponse,
    SourceWorkDetailResponse,
)


class FakeSourceService:
    def get_source_work(self, source_work_id: int) -> SourceWorkDetailResponse:
        if source_work_id != 1:
            raise ApplicationError(
                code=ErrorCode.SOURCE_WORK_NOT_FOUND,
                message="source work was not found",
                details={"source_work_id": source_work_id},
            )
        return SourceWorkDetailResponse(
            source_work_id=1,
            text_code=100,
            title_zh="三國志",
            title_en="Records of the Three Kingdoms",
            source_name="CBDB",
            source_table="TEXT_CODES",
            source_pk="100",
            ref_count=3,
            encounter_count=2,
        )

    def get_source_ref(self, source_ref_id: int) -> SourceRefDetailResponse:
        if source_ref_id != 10:
            raise ApplicationError(
                code=ErrorCode.SOURCE_REF_NOT_FOUND,
                message="source ref was not found",
                details={"source_ref_id": source_ref_id},
            )
        return SourceRefDetailResponse(
            source_ref_id=10,
            source_work=self.get_source_work(1),
            ref_source_table="BIOG_MAIN",
            ref_source_pk="25403",
            pages="12a",
            notes="原始引用",
            source_name="CBDB",
            source_table="BIOG_SOURCE_DATA",
            source_pk="10",
            linked_encounter_evidence=[
                LinkedEncounterEvidenceResponse(
                    evidence_id=55,
                    encounter_id=UUID("00000000-0000-0000-0000-000000000101"),
                    evidence_kind="candidate",
                    evidence_summary="有直接交往證據",
                    pages="12a",
                    created_at=datetime(2026, 6, 19, tzinfo=UTC),
                )
            ],
        )


def test_source_work_route_returns_payload() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_source_service] = lambda: FakeSourceService()

    with TestClient(app) as client:
        response = client.get("/api/v1/source-works/1")

    assert response.status_code == 200
    body = response.json()
    assert body["source_work_id"] == 1
    assert body["title_zh"] == "三國志"
    assert body["encounter_count"] == 2


def test_source_ref_route_returns_payload() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_source_service] = lambda: FakeSourceService()

    with TestClient(app) as client:
        response = client.get("/api/v1/source-refs/10")

    assert response.status_code == 200
    body = response.json()
    assert body["source_ref_id"] == 10
    assert body["source_work"]["source_work_id"] == 1
    assert body["linked_encounter_evidence"][0]["evidence_id"] == 55


def test_source_routes_return_404_when_missing() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_source_service] = lambda: FakeSourceService()

    with TestClient(app) as client:
        work_response = client.get("/api/v1/source-works/999")
        ref_response = client.get("/api/v1/source-refs/999")

    assert work_response.status_code == 404
    assert work_response.json()["error"]["code"] == "source_work_not_found"
    assert ref_response.status_code == 404
    assert ref_response.json()["error"]["code"] == "source_ref_not_found"
