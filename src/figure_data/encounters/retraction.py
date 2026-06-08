from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.db.enums import EncounterStatus, ReviewStatus
from figure_data.encounters.types import (
    EncounterOperationError,
    EncounterRetractionOptions,
    EncounterRetractionResult,
)

_CANDIDATE_TABLES = {"relationship_candidates", "kinship_candidates"}


def retract_encounter(
    session: Session,
    options: EncounterRetractionOptions,
) -> EncounterRetractionResult:
    status = _load_encounter_status(session, options.encounter_id)
    if status is None:
        raise EncounterOperationError(f"encounter not found: {options.encounter_id}")
    if status == EncounterStatus.RETRACTED.value and not options.force:
        raise EncounterOperationError("encounter is already retracted; pass force to update note")
    now = datetime.now(UTC)
    _mark_encounter_retracted(session, options, now)
    linked_candidates = _load_linked_candidates(session, options.encounter_id)
    updated_count = _mark_linked_candidates_needing_review(
        session,
        linked_candidates,
        reviewed_by=options.reviewed_by,
        review_note=options.note,
        reviewed_at=now,
    )
    return EncounterRetractionResult(
        encounter_id=options.encounter_id,
        status=EncounterStatus.RETRACTED,
        path_eligible=False,
        linked_candidates_updated=updated_count,
    )


def _load_encounter_status(session: Session, encounter_id: UUID) -> str | None:
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
    return None if row is None else str(row["status"])


def _mark_encounter_retracted(
    session: Session,
    options: EncounterRetractionOptions,
    reviewed_at: datetime,
) -> None:
    session.execute(
        text(
            """
            update figure_data.encounters
            set status = :status,
                path_eligible = false,
                reviewed_by = :reviewed_by,
                reviewed_at = :reviewed_at,
                review_note = :review_note,
                updated_at = :reviewed_at
            where id = :encounter_id
            """
        ),
        {
            "encounter_id": options.encounter_id,
            "status": EncounterStatus.RETRACTED.value,
            "reviewed_by": options.reviewed_by,
            "reviewed_at": reviewed_at,
            "review_note": options.note,
        },
    )


def _load_linked_candidates(session: Session, encounter_id: UUID) -> list[tuple[str, int]]:
    rows = session.execute(
        text(
            """
            select candidate_table, candidate_id
            from figure_data.encounter_evidence
            where encounter_id = :encounter_id
              and candidate_table is not null
              and candidate_id is not null
            """
        ),
        {"encounter_id": encounter_id},
    ).mappings().all()
    return [(str(row["candidate_table"]), int(row["candidate_id"])) for row in rows]


def _mark_linked_candidates_needing_review(
    session: Session,
    linked_candidates: list[tuple[str, int]],
    *,
    reviewed_by: str,
    review_note: str,
    reviewed_at: datetime,
) -> int:
    updated_count = 0
    for table_name, candidate_id in linked_candidates:
        if table_name not in _CANDIDATE_TABLES:
            continue
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
                "review_status": ReviewStatus.NEEDS_REVIEW.value,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
                "review_note": review_note,
            },
        )
        updated_count += 1
    return updated_count
