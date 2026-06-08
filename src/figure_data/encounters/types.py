from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from figure_data.db.enums import CertaintyLevel, EncounterKind, EncounterStatus
from figure_data.review.types import CandidateKind, CandidatePerson, CandidateSourceRef


class EncounterOperationError(ValueError):
    """Raised when encounter promotion, query, or retraction is invalid."""


@dataclass(frozen=True)
class EncounterPromotionOptions:
    candidate_kind: CandidateKind
    candidate_id: int
    reviewed_by: str
    evidence_summary: str
    review_note: str | None = None
    encounter_kind: EncounterKind | None = None
    certainty_level: CertaintyLevel | None = None
    path_eligible: bool | None = None
    allow_non_default: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewed_by",
            require_non_blank(self.reviewed_by, field_name="reviewed_by"),
        )
        object.__setattr__(
            self,
            "evidence_summary",
            require_non_blank(self.evidence_summary, field_name="evidence_summary"),
        )
        if self.review_note is not None:
            normalized_note = self.review_note.strip()
            object.__setattr__(self, "review_note", normalized_note or None)


@dataclass(frozen=True)
class EncounterPromotionResult:
    encounter_id: UUID
    candidate_kind: CandidateKind
    candidate_id: int
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    reused_existing: bool


@dataclass(frozen=True)
class EncounterSummary:
    encounter_id: UUID
    person_a_name: str | None
    person_b_name: str | None
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    source_work_id: int | None
    pages: str | None
    status: str
    reviewed_by: str
    reviewed_at: datetime


@dataclass(frozen=True)
class EncounterEvidenceDetail:
    evidence_id: int
    candidate_table: str | None
    candidate_id: int | None
    source_ref_id: int | None
    source_work_id: int | None
    pages: str | None
    evidence_kind: str
    evidence_summary: str
    created_at: datetime


@dataclass(frozen=True)
class EncounterDetail:
    encounter_id: UUID
    person_a: CandidatePerson
    person_b: CandidatePerson
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    source_work_id: int | None
    pages: str | None
    evidence_summary: str
    review_note: str | None
    status: str
    reviewed_by: str
    reviewed_at: datetime
    created_at: datetime
    updated_at: datetime
    evidence: list[EncounterEvidenceDetail]
    source_refs: list[CandidateSourceRef]


@dataclass(frozen=True)
class EncounterRetractionOptions:
    encounter_id: UUID
    reviewed_by: str
    note: str
    force: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewed_by",
            require_non_blank(self.reviewed_by, field_name="reviewed_by"),
        )
        object.__setattr__(self, "note", require_non_blank(self.note, field_name="note"))


@dataclass(frozen=True)
class EncounterRetractionResult:
    encounter_id: UUID
    status: EncounterStatus
    path_eligible: bool
    linked_candidates_updated: int


def require_non_blank(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise EncounterOperationError(f"{field_name} is required")
    return normalized
