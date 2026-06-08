from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.db.enums import CertaintyLevel, EncounterKind, EncounterStatus, ReviewStatus
from figure_data.encounters.types import (
    EncounterOperationError,
    EncounterPromotionOptions,
    EncounterPromotionResult,
)
from figure_data.review.candidate_detail import get_candidate_detail
from figure_data.review.types import CandidateDetail, CandidateKind, candidate_table_name


def promote_candidate_to_encounter(
    session: Session,
    options: EncounterPromotionOptions,
) -> EncounterPromotionResult:
    detail = get_candidate_detail(session, options.candidate_kind, options.candidate_id)
    _validate_candidate_can_be_promoted(detail, options)
    encounter_kind = _resolve_encounter_kind(detail, options)
    certainty_level = _resolve_certainty_level(detail, options)
    path_eligible = _resolve_path_eligible(detail, options, certainty_level)
    person_a_id, person_b_id = _ordered_person_ids(detail)
    now = datetime.now(UTC)
    existing_id = _find_existing_encounter(
        session,
        person_a_id=person_a_id,
        person_b_id=person_b_id,
        encounter_kind=encounter_kind,
        time_start_year=None,
        time_end_year=None,
        source_work_id=detail.source_work_id,
        pages=detail.pages,
    )
    if existing_id is None:
        encounter_id = uuid4()
        _insert_encounter(
            session,
            encounter_id=encounter_id,
            detail=detail,
            person_a_id=person_a_id,
            person_b_id=person_b_id,
            encounter_kind=encounter_kind,
            certainty_level=certainty_level,
            path_eligible=path_eligible,
            reviewed_by=options.reviewed_by,
            evidence_summary=options.evidence_summary,
            review_note=options.review_note,
            now=now,
        )
        reused_existing = False
    else:
        encounter_id = existing_id
        reused_existing = True
    _insert_encounter_evidence(
        session,
        encounter_id=encounter_id,
        detail=detail,
        evidence_summary=options.evidence_summary,
        now=now,
    )
    _mark_candidate_promoted(
        session,
        detail=detail,
        encounter_id=encounter_id,
        reviewed_by=options.reviewed_by,
        review_note=options.review_note or options.evidence_summary,
        now=now,
    )
    return EncounterPromotionResult(
        encounter_id=encounter_id,
        candidate_kind=options.candidate_kind,
        candidate_id=options.candidate_id,
        encounter_kind=encounter_kind.value,
        certainty_level=certainty_level.value,
        path_eligible=path_eligible,
        reused_existing=reused_existing,
    )


def _validate_candidate_can_be_promoted(
    detail: CandidateDetail,
    options: EncounterPromotionOptions,
) -> None:
    if detail.person_a.person_id is None or detail.person_b.person_id is None:
        raise EncounterOperationError("candidate is missing person ids")
    if detail.person_a.person_id == detail.person_b.person_id:
        raise EncounterOperationError("candidate is a self-loop")
    if detail.review_status == ReviewStatus.PROMOTED_TO_ENCOUNTER.value:
        raise EncounterOperationError("candidate is already promoted")
    if detail.promoted_encounter_id is not None:
        raise EncounterOperationError("candidate is already linked to an encounter")
    if detail.candidate_strength in {"background", "not_applicable"}:
        raise EncounterOperationError("candidate strength cannot be promoted")
    if not detail.promotion_readiness.default_promotable:
        if not options.allow_non_default:
            raise EncounterOperationError("candidate requires --allow-non-default")
        if not options.review_note:
            raise EncounterOperationError("non-default promotion requires review_note")


def _resolve_encounter_kind(
    detail: CandidateDetail,
    options: EncounterPromotionOptions,
) -> EncounterKind:
    if options.encounter_kind is not None:
        return options.encounter_kind
    if detail.candidate_kind is CandidateKind.KINSHIP:
        return EncounterKind.FAMILY_CONTACT
    if detail.candidate_basis == "co_presence_likely":
        return EncounterKind.CO_PRESENCE
    return EncounterKind.DIRECT_INTERACTION


def _resolve_certainty_level(
    detail: CandidateDetail,
    options: EncounterPromotionOptions,
) -> CertaintyLevel:
    if options.certainty_level is not None:
        return options.certainty_level
    if detail.promotion_readiness.default_promotable:
        return CertaintyLevel.HIGH
    if detail.candidate_strength == "medium":
        return CertaintyLevel.MEDIUM
    return CertaintyLevel.LOW


def _resolve_path_eligible(
    detail: CandidateDetail,
    options: EncounterPromotionOptions,
    certainty_level: CertaintyLevel,
) -> bool:
    if options.path_eligible is None:
        return detail.promotion_readiness.default_path_eligible
    if options.path_eligible:
        if not detail.promotion_readiness.default_path_eligible:
            raise EncounterOperationError("non-default candidates cannot be path_eligible")
        if certainty_level is not CertaintyLevel.HIGH:
            raise EncounterOperationError("path_eligible requires high certainty")
    return options.path_eligible


def _ordered_person_ids(detail: CandidateDetail) -> tuple[UUID, UUID]:
    person_a_id = detail.person_a.person_id
    person_b_id = detail.person_b.person_id
    if person_a_id is None or person_b_id is None:
        raise EncounterOperationError("candidate is missing person ids")
    ordered = sorted([person_a_id, person_b_id], key=str)
    return ordered[0], ordered[1]


def _find_existing_encounter(
    session: Session,
    *,
    person_a_id: UUID,
    person_b_id: UUID,
    encounter_kind: EncounterKind,
    time_start_year: int | None,
    time_end_year: int | None,
    source_work_id: int | None,
    pages: str | None,
) -> UUID | None:
    value = session.execute(
        text(
            """
            select e.id
            from figure_data.encounters e
            where e.person_a_id = :person_a_id
              and e.person_b_id = :person_b_id
              and e.encounter_kind = :encounter_kind
              and e.status = 'active'
              and e.time_start_year is not distinct from :time_start_year
              and e.time_end_year is not distinct from :time_end_year
              and e.source_work_id is not distinct from :source_work_id
              and e.pages is not distinct from :pages
            order by e.created_at
            limit 1
            """
        ),
        {
            "person_a_id": person_a_id,
            "person_b_id": person_b_id,
            "encounter_kind": encounter_kind.value,
            "time_start_year": time_start_year,
            "time_end_year": time_end_year,
            "source_work_id": source_work_id,
            "pages": pages,
        },
    ).scalar_one_or_none()
    return value if isinstance(value, UUID) or value is None else UUID(str(value))


def _insert_encounter(
    session: Session,
    *,
    encounter_id: UUID,
    detail: CandidateDetail,
    person_a_id: UUID,
    person_b_id: UUID,
    encounter_kind: EncounterKind,
    certainty_level: CertaintyLevel,
    path_eligible: bool,
    reviewed_by: str,
    evidence_summary: str,
    review_note: str | None,
    now: datetime,
) -> None:
    session.execute(
        text(
            """
            insert into figure_data.encounters (
              id, person_a_id, person_b_id, person_a_cbdb_id, person_b_cbdb_id,
              encounter_kind, certainty_level, path_eligible,
              time_start_year, time_end_year, source_work_id, pages,
              evidence_summary, review_note, status,
              reviewed_by, reviewed_at, created_at, updated_at
            ) values (
              :id, :person_a_id, :person_b_id, :person_a_cbdb_id, :person_b_cbdb_id,
              :encounter_kind, :certainty_level, :path_eligible,
              null, null, :source_work_id, :pages,
              :evidence_summary, :review_note, :status,
              :reviewed_by, :now, :now, :now
            )
            """
        ),
        {
            "id": encounter_id,
            "person_a_id": person_a_id,
            "person_b_id": person_b_id,
            "person_a_cbdb_id": detail.person_a.cbdb_id,
            "person_b_cbdb_id": detail.person_b.cbdb_id,
            "encounter_kind": encounter_kind.value,
            "certainty_level": certainty_level.value,
            "path_eligible": path_eligible,
            "source_work_id": detail.source_work_id,
            "pages": detail.pages,
            "evidence_summary": evidence_summary,
            "review_note": review_note,
            "status": EncounterStatus.ACTIVE.value,
            "reviewed_by": reviewed_by,
            "now": now,
        },
    )


def _insert_encounter_evidence(
    session: Session,
    *,
    encounter_id: UUID,
    detail: CandidateDetail,
    evidence_summary: str,
    now: datetime,
) -> None:
    first_source_ref = detail.source_refs[0] if detail.source_refs else None
    session.execute(
        text(
            """
            insert into figure_data.encounter_evidence (
              encounter_id, candidate_table, candidate_id, source_ref_id,
              source_work_id, pages, evidence_kind, evidence_summary,
              raw_snapshot, created_at
            ) values (
              :encounter_id, :candidate_table, :candidate_id, :source_ref_id,
              :source_work_id, :pages, :evidence_kind, :evidence_summary,
              cast(:raw_snapshot as jsonb), :now
            )
            on conflict on constraint uq_encounter_evidence_candidate do nothing
            """
        ),
        {
            "encounter_id": encounter_id,
            "candidate_table": candidate_table_name(detail.candidate_kind),
            "candidate_id": detail.candidate_id,
            "source_ref_id": first_source_ref.source_ref_id if first_source_ref else None,
            "source_work_id": detail.source_work_id,
            "pages": detail.pages,
            "evidence_kind": "candidate",
            "evidence_summary": evidence_summary,
            "raw_snapshot": _raw_snapshot_json(detail),
            "now": now,
        },
    )


def _mark_candidate_promoted(
    session: Session,
    *,
    detail: CandidateDetail,
    encounter_id: UUID,
    reviewed_by: str,
    review_note: str,
    now: datetime,
) -> None:
    table_name = candidate_table_name(detail.candidate_kind)
    session.execute(
        text(
            f"""
            update figure_data.{table_name}
            set review_status = :review_status,
                promoted_encounter_id = :encounter_id,
                reviewed_by = :reviewed_by,
                reviewed_at = :reviewed_at,
                review_note = :review_note
            where id = :candidate_id
            """
        ),
        {
            "candidate_id": detail.candidate_id,
            "review_status": ReviewStatus.PROMOTED_TO_ENCOUNTER.value,
            "encounter_id": encounter_id,
            "reviewed_by": reviewed_by,
            "reviewed_at": now,
            "review_note": review_note,
        },
    )


def _raw_snapshot_json(detail: CandidateDetail) -> str:
    snapshot = {
        **detail.raw_cbdb_snapshot,
        "candidate_kind": detail.candidate_kind.value,
        "candidate_id": detail.candidate_id,
        "candidate_strength": detail.candidate_strength,
        "candidate_basis": detail.candidate_basis,
        "source_refs": [
            {
                "source_ref_id": source_ref.source_ref_id,
                "source_work_id": source_ref.source_work_id,
                "pages": source_ref.pages,
                "notes": source_ref.notes,
            }
            for source_ref in detail.source_refs
        ],
    }
    return json.dumps(snapshot, ensure_ascii=False, default=str)
