from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_review_service
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    ReviewActionResponse,
    ReviewCandidateDetailResponse,
    ReviewCandidateListResponse,
    ReviewCandidatePersonResponse,
    ReviewCandidateRelationResponse,
    ReviewCandidateSummary,
    ReviewLinkedEncounterResponse,
    ReviewNeedsReviewRequest,
    ReviewPromoteRequest,
    ReviewPromotionReadinessResponse,
    ReviewRejectRequest,
)
from figure_chain.services.review import ReviewCandidateFilters

PERSON_ID = UUID("00000000-0000-0000-0000-000000000001")


class FakeReviewService:
    def __init__(self) -> None:
        self.filters: ReviewCandidateFilters | None = None

    def list_candidates(self, filters: ReviewCandidateFilters) -> ReviewCandidateListResponse:
        self.filters = filters
        return ReviewCandidateListResponse(
            items=[
                ReviewCandidateSummary(
                    kind="relationship",
                    candidate_id=10,
                    person_a=_person(),
                    person_b=_person(),
                    relation_type="同僚",
                    time_summary="12a",
                    place_summary=None,
                    status="unreviewed",
                    confidence=0.9,
                    evidence_count=0,
                    source_count=1,
                    promotion_readiness=_readiness(),
                    latest_ai_job_status=None,
                    has_ai_suggestion=False,
                )
            ],
            limit=filters.limit,
            offset=filters.offset,
            count=1,
        )

    def get_candidate(self, kind: str, candidate_id: int) -> ReviewCandidateDetailResponse:
        if kind == "invalid":
            raise ApplicationError(
                code=ErrorCode.CANDIDATE_INVALID_KIND,
                message="candidate kind is not supported",
                details={"kind": kind},
            )
        if candidate_id != 10:
            raise ApplicationError(
                code=ErrorCode.CANDIDATE_NOT_FOUND,
                message="candidate was not found",
                details={"kind": kind, "candidate_id": candidate_id},
            )
        return ReviewCandidateDetailResponse(
            kind=kind,
            candidate_id=candidate_id,
            person_a=_person(),
            person_b=_person(),
            relation=ReviewCandidateRelationResponse(
                relation_type="同僚",
                basis="direct_interaction_likely",
                strength="high",
                notes=None,
                source_name="assoc_data",
                source_table="assoc_data",
                source_pk="10",
            ),
            time=None,
            place=None,
            status="unreviewed",
            confidence=0.9,
            source_refs=[],
            evidence=[],
            promotion_readiness=_readiness(),
            linked_encounter=None,
            latest_ai_suggestion=None,
            ai_jobs=[],
        )

    def promote_candidate(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewPromoteRequest,
    ) -> ReviewActionResponse:
        if candidate_id == 99:
            raise ApplicationError(
                code=ErrorCode.CANDIDATE_NOT_PROMOTABLE,
                message="candidate requires --allow-non-default",
                details={"kind": kind, "candidate_id": candidate_id},
            )
        return ReviewActionResponse(
            kind=kind,
            candidate_id=candidate_id,
            status="promoted_to_encounter",
            reviewed_by=request.reviewed_by,
            encounter=ReviewLinkedEncounterResponse(
                encounter_id=UUID("00000000-0000-0000-0000-000000000003"),
                status="active",
            ),
            message=None,
        )

    def reject_candidate(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewRejectRequest,
    ) -> ReviewActionResponse:
        return ReviewActionResponse(
            kind=kind,
            candidate_id=candidate_id,
            status="rejected",
            reviewed_by=request.reviewed_by,
            encounter=None,
            message=request.reason,
        )

    def mark_candidate_needs_review(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewNeedsReviewRequest,
    ) -> ReviewActionResponse:
        return ReviewActionResponse(
            kind=kind,
            candidate_id=candidate_id,
            status="needs_review",
            reviewed_by=request.reviewed_by,
            encounter=None,
            message=request.note,
        )


def test_review_candidates_router_returns_list_response() -> None:
    service = FakeReviewService()
    app = _router_app(service)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/review/candidates",
            params={
                "kind": "relationship",
                "status": "unreviewed",
                "min_confidence": "0.8",
                "person_id": str(PERSON_ID),
                "limit": "25",
                "offset": "5",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["candidate_id"] == 10
    assert service.filters == ReviewCandidateFilters(
        kind="relationship",
        status="unreviewed",
        min_confidence=0.8,
        person_id=PERSON_ID,
        limit=25,
        offset=5,
    )


def test_review_candidate_router_returns_detail_response() -> None:
    app = _router_app(FakeReviewService())

    with TestClient(app) as client:
        response = client.get("/api/v1/review/candidates/relationship/10")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "relationship"
    assert body["candidate_id"] == 10
    assert body["latest_ai_suggestion"] is None
    assert body["ai_jobs"] == []


def test_review_candidate_router_returns_not_found_error() -> None:
    app = _router_app(FakeReviewService())

    with TestClient(app) as client:
        response = client.get("/api/v1/review/candidates/relationship/999")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "candidate_not_found",
            "message": "candidate was not found",
            "details": {"kind": "relationship", "candidate_id": 999},
        }
    }


def test_review_candidate_router_returns_invalid_kind_error() -> None:
    app = _router_app(FakeReviewService())

    with TestClient(app) as client:
        response = client.get("/api/v1/review/candidates/invalid/10")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "candidate_invalid_kind"


def test_review_candidates_router_rejects_limit_over_max() -> None:
    app = _router_app(FakeReviewService())

    with TestClient(app) as client:
        response = client.get("/api/v1/review/candidates", params={"limit": "201"})

    assert response.status_code == 422


def test_review_candidate_promote_route_returns_action_response() -> None:
    app = _router_app(FakeReviewService())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/review/candidates/relationship/10/promote",
            json={
                "reviewed_by": "lyl",
                "evidence_summary": "有明确见面证据",
                "note": "人工确认",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "promoted_to_encounter"
    assert body["encounter"]["status"] == "active"


def test_review_candidate_reject_route_returns_action_response() -> None:
    app = _router_app(FakeReviewService())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/review/candidates/relationship/10/reject",
            json={"reviewed_by": "lyl", "reason": "证据不足"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_review_candidate_needs_review_route_returns_action_response() -> None:
    app = _router_app(FakeReviewService())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/review/candidates/relationship/10/needs-review",
            json={"reviewed_by": "lyl", "note": "稍后复核"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_review"


def test_review_candidate_promote_route_returns_stable_failure() -> None:
    app = _router_app(FakeReviewService())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/review/candidates/relationship/99/promote",
            json={"reviewed_by": "lyl", "evidence_summary": "证据摘要"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "candidate_not_promotable"


def _router_app(service: FakeReviewService) -> FastAPI:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_review_service] = lambda: service
    return app


def _person() -> ReviewCandidatePersonResponse:
    return ReviewCandidatePersonResponse(
        person_id=str(PERSON_ID),
        cbdb_id=780,
        display_name="許幾",
        primary_name_zh_hant="許幾",
        primary_name_zh_hans="许几",
        primary_name_romanized="Xu Ji",
        birth_year=None,
        death_year=None,
    )


def _readiness() -> ReviewPromotionReadinessResponse:
    return ReviewPromotionReadinessResponse(
        default_promotable=True,
        default_path_eligible=True,
        reasons=[],
    )
