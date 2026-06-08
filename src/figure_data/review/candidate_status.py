from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.db.enums import EncounterStatus
from figure_data.review.types import (
    CandidateKind,
    CandidateReviewError,
    CandidateReviewStatus,
    CandidateStatusChange,
    candidate_table_name,
    require_review_text,
)


def reject_candidate(
    session: Session,
    kind: CandidateKind,
    candidate_id: int,
    *,
    reviewed_by: str,
    note: str,
) -> CandidateStatusChange:
    return _update_candidate_review_status(
        session,
        kind,
        candidate_id,
        review_status=CandidateReviewStatus.REJECTED,
        reviewed_by=reviewed_by,
        note=note,
    )


def mark_candidate_for_review(
    session: Session,
    kind: CandidateKind,
    candidate_id: int,
    *,
    reviewed_by: str,
    note: str,
) -> CandidateStatusChange:
    return _update_candidate_review_status(
        session,
        kind,
        candidate_id,
        review_status=CandidateReviewStatus.NEEDS_REVIEW,
        reviewed_by=reviewed_by,
        note=note,
    )


def _update_candidate_review_status(
    session: Session,
    kind: CandidateKind,
    candidate_id: int,
    *,
    review_status: CandidateReviewStatus,
    reviewed_by: str,
    note: str,
) -> CandidateStatusChange:
    normalized_reviewed_by = require_review_text(reviewed_by, field_name="reviewed_by")
    normalized_note = require_review_text(note, field_name="review_note")
    table_name = candidate_table_name(kind)

    existing = session.execute(
        text(
            f"""
            select review_status, promoted_encounter_id
            from figure_data.{table_name}
            where id = :candidate_id
            """
        ),
        {"candidate_id": candidate_id},
    ).mappings().one_or_none()
    if existing is None:
        raise CandidateReviewError(f"candidate not found: {kind.value}:{candidate_id}")
    if existing["review_status"] == CandidateReviewStatus.PROMOTED_TO_ENCOUNTER.value:
        raise CandidateReviewError("candidate is already promoted; retract the encounter first")
    if existing["promoted_encounter_id"] is not None:
        _ensure_linked_encounter_is_not_active(session, existing["promoted_encounter_id"])

    session.execute(
        text(
            f"""
            update figure_data.{table_name}
            set review_status = :review_status,
                reviewed_by = :reviewed_by,
                reviewed_at = :reviewed_at,
                review_note = :review_note
            where id = :candidate_id
            """
        ),
        {
            "candidate_id": candidate_id,
            "review_status": review_status.value,
            "reviewed_by": normalized_reviewed_by,
            "reviewed_at": datetime.now(UTC),
            "review_note": normalized_note,
        },
    )
    return CandidateStatusChange(
        candidate_kind=kind,
        candidate_id=candidate_id,
        review_status=review_status,
        reviewed_by=normalized_reviewed_by,
        review_note=normalized_note,
    )


def _ensure_linked_encounter_is_not_active(session: Session, encounter_id: UUID) -> None:
    row = session.execute(
        text(
            """
            select status
            from figure_data.encounters
            where id = :encounter_id
            """
        ),
        {"encounter_id": encounter_id},
    ).mappings().one_or_none()
    if row is None:
        raise CandidateReviewError("candidate is linked to a missing encounter")
    if row["status"] == EncounterStatus.ACTIVE.value:
        raise CandidateReviewError("candidate is linked to an active encounter; retract it first")
