from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from figure_chain.access import OperationContext
from figure_chain.dependencies import get_admin_review_service, require_operator_context
from figure_chain.schemas import (
    AdminEncounterRetractRequest,
    AdminEncounterRetractResponse,
    AdminReviewActionResponse,
    ReviewCandidateDetailResponse,
    ReviewCandidateListResponse,
    ReviewNeedsReviewRequest,
    ReviewPromoteRequest,
    ReviewRejectRequest,
)
from figure_chain.services.admin_review import AdminReviewService
from figure_chain.services.review import ReviewCandidateFilters

router = APIRouter(prefix="/api/v1/admin/review", tags=["admin"])


@router.get("/candidates", response_model=ReviewCandidateListResponse)
def list_admin_review_candidates(
    service: Annotated[AdminReviewService, Depends(get_admin_review_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
    kind: str | None = None,
    status: str | None = None,
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    person_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ReviewCandidateListResponse:
    return service.list_candidates(
        ReviewCandidateFilters(
            kind=kind,
            status=status,
            min_confidence=min_confidence,
            person_id=person_id,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/candidates/{kind}/{candidate_id}", response_model=ReviewCandidateDetailResponse)
def get_admin_review_candidate(
    kind: str,
    candidate_id: int,
    service: Annotated[AdminReviewService, Depends(get_admin_review_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> ReviewCandidateDetailResponse:
    return service.get_candidate(kind, candidate_id)


@router.post(
    "/candidates/{kind}/{candidate_id}/promote",
    response_model=AdminReviewActionResponse,
)
def promote_admin_review_candidate(
    kind: str,
    candidate_id: int,
    request: ReviewPromoteRequest,
    service: Annotated[AdminReviewService, Depends(get_admin_review_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminReviewActionResponse:
    return service.promote_candidate(kind, candidate_id, request)


@router.post(
    "/candidates/{kind}/{candidate_id}/reject",
    response_model=AdminReviewActionResponse,
)
def reject_admin_review_candidate(
    kind: str,
    candidate_id: int,
    request: ReviewRejectRequest,
    service: Annotated[AdminReviewService, Depends(get_admin_review_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminReviewActionResponse:
    return service.reject_candidate(kind, candidate_id, request)


@router.post(
    "/candidates/{kind}/{candidate_id}/needs-review",
    response_model=AdminReviewActionResponse,
)
def mark_admin_review_candidate_needs_review(
    kind: str,
    candidate_id: int,
    request: ReviewNeedsReviewRequest,
    service: Annotated[AdminReviewService, Depends(get_admin_review_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminReviewActionResponse:
    return service.mark_candidate_needs_review(kind, candidate_id, request)


@router.post(
    "/encounters/{encounter_id}/retract",
    response_model=AdminEncounterRetractResponse,
)
def retract_admin_encounter(
    encounter_id: UUID,
    request: AdminEncounterRetractRequest,
    service: Annotated[AdminReviewService, Depends(get_admin_review_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminEncounterRetractResponse:
    return service.retract_encounter(
        encounter_id,
        reviewed_by=request.reviewed_by,
        note=request.note,
        force=request.force,
    )
