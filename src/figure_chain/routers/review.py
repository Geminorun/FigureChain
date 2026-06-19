from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from figure_chain.dependencies import get_review_service, require_reviewer_context
from figure_chain.schemas import (
    ReviewActionResponse,
    ReviewCandidateDetailResponse,
    ReviewCandidateListResponse,
    ReviewNeedsReviewRequest,
    ReviewPromoteRequest,
    ReviewRejectRequest,
)
from figure_chain.services.review import ReviewCandidateFilters, ReviewService

router = APIRouter(prefix="/api/v1/review", tags=["review"])


@router.get("/candidates", response_model=ReviewCandidateListResponse)
def list_review_candidates(
    service: Annotated[ReviewService, Depends(get_review_service)],
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
def get_review_candidate(
    kind: str,
    candidate_id: int,
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewCandidateDetailResponse:
    return service.get_candidate(kind, candidate_id)


@router.post("/candidates/{kind}/{candidate_id}/promote", response_model=ReviewActionResponse)
def promote_review_candidate(
    kind: str,
    candidate_id: int,
    request: ReviewPromoteRequest,
    _context: Annotated[object, Depends(require_reviewer_context)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewActionResponse:
    return service.promote_candidate(kind, candidate_id, request)


@router.post("/candidates/{kind}/{candidate_id}/reject", response_model=ReviewActionResponse)
def reject_review_candidate(
    kind: str,
    candidate_id: int,
    request: ReviewRejectRequest,
    _context: Annotated[object, Depends(require_reviewer_context)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewActionResponse:
    return service.reject_candidate(kind, candidate_id, request)


@router.post("/candidates/{kind}/{candidate_id}/needs-review", response_model=ReviewActionResponse)
def mark_review_candidate_needs_review(
    kind: str,
    candidate_id: int,
    request: ReviewNeedsReviewRequest,
    _context: Annotated[object, Depends(require_reviewer_context)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewActionResponse:
    return service.mark_candidate_needs_review(kind, candidate_id, request)
