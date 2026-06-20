from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient
from httpx import Response

from figure_chain.app import create_app
from figure_chain.dependencies import get_admin_review_service
from figure_chain.schemas import (
    AdminEncounterRetractResponse,
    AdminEncounterRetractResultResponse,
    AdminReviewActionResponse,
    ReviewActionResponse,
    ReviewCandidateDetailResponse,
    ReviewCandidateListResponse,
    ReviewCandidatePersonResponse,
    ReviewCandidateRelationResponse,
    ReviewCandidateTimeResponse,
    ReviewPromotionReadinessResponse,
)
from figure_chain.services.review import ReviewCandidateFilters

OPERATION_ID = UUID("00000000-0000-0000-0000-000000000901")
ENCOUNTER_ID = UUID("00000000-0000-0000-0000-000000000003")
NOW = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
OPERATOR_HEADERS = {"x-figure-role": "operator", "x-figure-actor": "local"}


class FakeAdminReviewService:
    def list_candidates(self, filters: ReviewCandidateFilters) -> ReviewCandidateListResponse:
        return ReviewCandidateListResponse(
            items=[],
            limit=filters.limit,
            offset=filters.offset,
            count=0,
        )

    def get_candidate(self, kind: str, candidate_id: int) -> ReviewCandidateDetailResponse:
        return _detail(kind=kind, candidate_id=candidate_id)

    def promote_candidate(
        self,
        kind: str,
        candidate_id: int,
        request: object,
    ) -> AdminReviewActionResponse:
        return _admin_action("promote_candidate", kind, candidate_id)

    def reject_candidate(
        self,
        kind: str,
        candidate_id: int,
        request: object,
    ) -> AdminReviewActionResponse:
        return _admin_action("reject_candidate", kind, candidate_id)

    def mark_candidate_needs_review(
        self,
        kind: str,
        candidate_id: int,
        request: object,
    ) -> AdminReviewActionResponse:
        return _admin_action("mark_candidate_needs_review", kind, candidate_id)

    def retract_encounter(
        self,
        encounter_id: UUID,
        *,
        reviewed_by: str,
        note: str,
        force: bool = False,
    ) -> AdminEncounterRetractResponse:
        return AdminEncounterRetractResponse(
            operation_id=OPERATION_ID,
            operation_type="retract_encounter",
            status="succeeded",
            result=AdminEncounterRetractResultResponse(
                encounter_id=encounter_id,
                status="retracted",
                path_eligible=False,
                linked_candidates_updated=1,
            ),
            preview=(
                f"figure-data retract-encounter --encounter-id {encounter_id} "
                f"--reviewed-by {reviewed_by}"
            ),
        )


def test_admin_review_api_requires_operator_role() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_review_service] = lambda: FakeAdminReviewService()
    try:
        response = TestClient(app).get(
            "/api/v1/admin/review/candidates",
            headers={"x-figure-role": "reviewer"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_admin_review_api_lists_candidates() -> None:
    response = _get("/api/v1/admin/review/candidates?kind=relationship&limit=25")

    assert response.status_code == 200
    assert response.json()["limit"] == 25
    assert response.json()["count"] == 0


def test_admin_review_api_gets_candidate() -> None:
    response = _get("/api/v1/admin/review/candidates/relationship/960655")

    assert response.status_code == 200
    assert response.json()["kind"] == "relationship"
    assert response.json()["candidate_id"] == 960655


def test_admin_review_api_promotes_candidate() -> None:
    response = _post(
        "/api/v1/admin/review/candidates/relationship/960655/promote",
        {"reviewed_by": "local", "evidence_summary": "证据摘要"},
    )

    assert response.status_code == 200
    assert response.json()["operation_type"] == "promote_candidate"
    assert response.json()["operation_id"] == str(OPERATION_ID)


def test_admin_review_api_rejects_candidate() -> None:
    response = _post(
        "/api/v1/admin/review/candidates/relationship/960655/reject",
        {"reviewed_by": "local", "reason": "证据不足"},
    )

    assert response.status_code == 200
    assert response.json()["operation_type"] == "reject_candidate"


def test_admin_review_api_marks_candidate_needs_review() -> None:
    response = _post(
        "/api/v1/admin/review/candidates/relationship/960655/needs-review",
        {"reviewed_by": "local", "note": "待查"},
    )

    assert response.status_code == 200
    assert response.json()["operation_type"] == "mark_candidate_needs_review"


def test_admin_review_api_retracts_encounter() -> None:
    response = _post(
        f"/api/v1/admin/review/encounters/{ENCOUNTER_ID}/retract",
        {"reviewed_by": "local", "note": "证据不足", "force": True},
    )

    assert response.status_code == 200
    assert response.json()["operation_type"] == "retract_encounter"
    assert response.json()["result"]["status"] == "retracted"


def _get(path: str) -> Response:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_review_service] = lambda: FakeAdminReviewService()
    try:
        return TestClient(app).get(path, headers=OPERATOR_HEADERS)
    finally:
        app.dependency_overrides.clear()


def _post(path: str, body: dict[str, object]) -> Response:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_review_service] = lambda: FakeAdminReviewService()
    try:
        return TestClient(app).post(path, headers=OPERATOR_HEADERS, json=body)
    finally:
        app.dependency_overrides.clear()


def _admin_action(operation_type: str, kind: str, candidate_id: int) -> AdminReviewActionResponse:
    return AdminReviewActionResponse(
        operation_id=OPERATION_ID,
        operation_type=operation_type,
        status="succeeded",
        action=ReviewActionResponse(
            kind=kind,
            candidate_id=candidate_id,
            status="reviewed",
            reviewed_by="local",
            encounter=None,
            message=None,
        ),
        preview=f"figure-data {operation_type}",
    )


def _detail(*, kind: str, candidate_id: int) -> ReviewCandidateDetailResponse:
    person = ReviewCandidatePersonResponse(
        person_id=None,
        cbdb_id=780,
        display_name="許幾",
        primary_name_zh_hant="許幾",
        primary_name_zh_hans=None,
        primary_name_romanized=None,
        birth_year=None,
        death_year=None,
    )
    return ReviewCandidateDetailResponse(
        kind=kind,
        candidate_id=candidate_id,
        person_a=person,
        person_b=person,
        relation=ReviewCandidateRelationResponse(
            relation_type="同僚",
            basis="direct_interaction_likely",
            strength="high",
            notes=None,
            source_name=None,
            source_table=None,
            source_pk=None,
        ),
        time=ReviewCandidateTimeResponse(summary=None, pages=None),
        place=None,
        status="unreviewed",
        confidence=0.9,
        source_refs=[],
        evidence=[],
        promotion_readiness=ReviewPromotionReadinessResponse(
            default_promotable=True,
            default_path_eligible=True,
            reasons=[],
        ),
        linked_encounter=None,
        latest_ai_suggestion=None,
        ai_jobs=[],
    )
