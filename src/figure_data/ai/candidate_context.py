from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.db.enums import CertaintyLevel, EncounterKind, EncounterStatus
from figure_data.review.types import CandidateDetail, CandidatePerson, CandidateSourceRef


class CandidateReviewPersonInput(BaseModel):
    person_id: str | None
    cbdb_id: int | None
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    external_ids: list[str] = Field(default_factory=list)


class CandidateReviewSourceRefInput(BaseModel):
    source_ref_id: int
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    notes: str | None


class CandidateReviewPromotionReadinessInput(BaseModel):
    default_promotable: bool
    default_path_eligible: bool
    reasons: list[str] = Field(default_factory=list)


class CandidateReviewCandidateInput(BaseModel):
    kind: str
    id: int
    candidate_strength: str
    candidate_basis: str
    relation_label: str | None
    source_work_id: int | None
    pages: str | None
    notes: str | None
    review_status: str
    reviewed_by: str | None
    review_note: str | None
    promoted_encounter_id: str | None
    source_name: str
    source_table: str
    source_pk: str
    has_active_path_encounter_for_pair: bool
    promotion_readiness: CandidateReviewPromotionReadinessInput


class CandidateReviewPromptInput(BaseModel):
    candidate: CandidateReviewCandidateInput
    person_a: CandidateReviewPersonInput
    person_b: CandidateReviewPersonInput
    source_refs: list[CandidateReviewSourceRefInput]


def build_candidate_review_prompt_input(
    session: Session,
    detail: CandidateDetail,
) -> CandidateReviewPromptInput:
    return candidate_review_prompt_input_from_detail(
        detail,
        has_active_path_encounter_for_pair=has_active_path_encounter_for_pair(
            session,
            detail,
        ),
    )


def candidate_review_prompt_input_from_detail(
    detail: CandidateDetail,
    *,
    has_active_path_encounter_for_pair: bool,
) -> CandidateReviewPromptInput:
    return CandidateReviewPromptInput(
        candidate=CandidateReviewCandidateInput(
            kind=detail.candidate_kind.value,
            id=detail.candidate_id,
            candidate_strength=detail.candidate_strength,
            candidate_basis=detail.candidate_basis,
            relation_label=detail.relation_label,
            source_work_id=detail.source_work_id,
            pages=detail.pages,
            notes=detail.notes,
            review_status=detail.review_status,
            reviewed_by=detail.reviewed_by,
            review_note=detail.review_note,
            promoted_encounter_id=(
                str(detail.promoted_encounter_id)
                if detail.promoted_encounter_id
                else None
            ),
            source_name=detail.source_name,
            source_table=detail.source_table,
            source_pk=detail.source_pk,
            has_active_path_encounter_for_pair=has_active_path_encounter_for_pair,
            promotion_readiness=CandidateReviewPromotionReadinessInput(
                default_promotable=detail.promotion_readiness.default_promotable,
                default_path_eligible=detail.promotion_readiness.default_path_eligible,
                reasons=detail.promotion_readiness.reasons,
            ),
        ),
        person_a=_person_input(detail.person_a),
        person_b=_person_input(detail.person_b),
        source_refs=[_source_ref_input(source_ref) for source_ref in detail.source_refs],
    )


def has_active_path_encounter_for_pair(session: Session, detail: CandidateDetail) -> bool:
    person_a_id = detail.person_a.person_id
    person_b_id = detail.person_b.person_id
    if person_a_id is None or person_b_id is None:
        return False
    value = session.execute(
        text(
            """
            select count(*) > 0
            from figure_data.encounters e
            where e.status = :status
              and e.path_eligible is true
              and e.certainty_level = :certainty_level
              and e.encounter_kind = :encounter_kind
              and (
                (e.person_a_id = :person_a_id and e.person_b_id = :person_b_id)
                or
                (e.person_a_id = :person_b_id and e.person_b_id = :person_a_id)
              )
            """
        ),
        {
            "status": EncounterStatus.ACTIVE.value,
            "certainty_level": CertaintyLevel.HIGH.value,
            "encounter_kind": EncounterKind.DIRECT_INTERACTION.value,
            "person_a_id": person_a_id,
            "person_b_id": person_b_id,
        },
    ).scalar_one()
    return bool(value)


def _person_input(person: CandidatePerson) -> CandidateReviewPersonInput:
    return CandidateReviewPersonInput(
        person_id=str(person.person_id) if person.person_id else None,
        cbdb_id=person.cbdb_id,
        primary_name_zh_hant=person.primary_name_zh_hant,
        primary_name_zh_hans=person.primary_name_zh_hans,
        primary_name_romanized=person.primary_name_romanized,
        birth_year=person.birth_year,
        death_year=person.death_year,
        external_ids=person.external_ids,
    )


def _source_ref_input(source_ref: CandidateSourceRef) -> CandidateReviewSourceRefInput:
    return CandidateReviewSourceRefInput(
        source_ref_id=source_ref.source_ref_id,
        source_work_id=source_ref.source_work_id,
        title_zh=source_ref.title_zh,
        title_en=source_ref.title_en,
        pages=source_ref.pages,
        notes=source_ref.notes,
    )
