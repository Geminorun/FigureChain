from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class CandidateReviewError(ValueError):
    """Raised when candidate review input or state is invalid."""


class CandidateKind(StrEnum):
    RELATIONSHIP = "relationship"
    KINSHIP = "kinship"


class CandidateReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    NEEDS_REVIEW = "needs_review"
    PROMOTED_TO_ENCOUNTER = "promoted_to_encounter"
    REJECTED = "rejected"


@dataclass(frozen=True)
class CandidatePerson:
    person_id: UUID | None
    cbdb_id: int | None
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    external_ids: list[str]


@dataclass(frozen=True)
class CandidateSummary:
    candidate_kind: CandidateKind
    candidate_id: int
    person_a_name: str | None
    person_b_name: str | None
    cbdb_person_a_id: int | None
    cbdb_person_b_id: int | None
    candidate_strength: str
    candidate_basis: str
    relation_label: str | None
    source_work_id: int | None
    pages: str | None
    review_status: str
    person_a_id: UUID | None = None
    person_b_id: UUID | None = None


@dataclass(frozen=True)
class CandidateSourceRef:
    source_ref_id: int
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    notes: str | None


@dataclass(frozen=True)
class PromotionReadiness:
    default_promotable: bool
    default_path_eligible: bool
    reasons: list[str]


@dataclass(frozen=True)
class CandidateDetail:
    candidate_kind: CandidateKind
    candidate_id: int
    person_a: CandidatePerson
    person_b: CandidatePerson
    candidate_strength: str
    candidate_basis: str
    relation_label: str | None
    source_work_id: int | None
    pages: str | None
    notes: str | None
    review_status: str
    reviewed_by: str | None
    review_note: str | None
    promoted_encounter_id: UUID | None
    source_name: str
    source_table: str
    source_pk: str
    raw_cbdb_snapshot: dict[str, object | None]
    source_refs: list[CandidateSourceRef]
    promotion_readiness: PromotionReadiness


@dataclass(frozen=True)
class CandidateStatusChange:
    candidate_kind: CandidateKind
    candidate_id: int
    review_status: CandidateReviewStatus
    reviewed_by: str
    review_note: str


def normalize_candidate_kind(value: str) -> CandidateKind:
    try:
        return CandidateKind(value)
    except ValueError as exc:
        raise CandidateReviewError(f"unsupported candidate kind: {value}") from exc


def candidate_table_name(kind: CandidateKind) -> str:
    if kind is CandidateKind.RELATIONSHIP:
        return "relationship_candidates"
    if kind is CandidateKind.KINSHIP:
        return "kinship_candidates"
    raise CandidateReviewError(f"unsupported candidate kind: {kind}")


def require_review_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise CandidateReviewError(f"{field_name} is required")
    return normalized
