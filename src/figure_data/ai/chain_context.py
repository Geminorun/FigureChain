from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from figure_data.ai.retrieval_context import AIRetrievalContextItem
from figure_data.db.enums import CertaintyLevel, EncounterKind, EncounterStatus
from figure_data.encounters.types import EncounterDetail
from figure_data.graph.types import ChainLookupResult


class ChainExplanationPersonInput(BaseModel):
    person_id: str
    display_name: str
    birth_year: int | None
    death_year: int | None
    cbdb_external_id: str | None


class ChainExplanationSourceRefInput(BaseModel):
    source_ref_id: int
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    notes: str | None


class ChainExplanationEvidenceInput(BaseModel):
    evidence_id: int
    candidate_table: str | None
    candidate_id: int | None
    source_ref_id: int | None
    source_work_id: int | None
    pages: str | None
    evidence_kind: str
    evidence_summary: str


class ChainExplanationEncounterInput(BaseModel):
    encounter_id: str
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    evidence_summary: str
    review_note: str | None
    source_work_id: int | None
    pages: str | None
    evidence: list[ChainExplanationEvidenceInput] = Field(default_factory=list)
    source_refs: list[ChainExplanationSourceRefInput] = Field(default_factory=list)


class ChainExplanationPromptInput(BaseModel):
    source_person_id: str
    target_person_id: str
    max_depth: int
    language: str
    people: list[ChainExplanationPersonInput]
    encounters: list[ChainExplanationEncounterInput]
    retrieval_context: list[AIRetrievalContextItem] = Field(default_factory=list)
    retrieval_context_status: Literal["available", "missing"] = "missing"


class InvalidChainContextError(ValueError):
    """Raised when a path cannot be explained from reviewed encounter evidence."""


def build_chain_explanation_prompt_input(
    *,
    result: ChainLookupResult,
    encounter_details: dict[str, EncounterDetail],
    language: str,
    retrieval_context: list[AIRetrievalContextItem] | None = None,
    retrieval_context_status: Literal["available", "missing"] = "missing",
) -> ChainExplanationPromptInput:
    if result.path is None:
        raise InvalidChainContextError("chain explanation requires a found path")
    people = [
        ChainExplanationPersonInput(
            person_id=person.person_id,
            display_name=person.display_name,
            birth_year=person.birth_year,
            death_year=person.death_year,
            cbdb_external_id=person.cbdb_external_id,
        )
        for person in result.path.people
    ]
    encounters: list[ChainExplanationEncounterInput] = []
    for edge in result.path.edges:
        detail = encounter_details.get(edge.encounter_id)
        if detail is None:
            raise InvalidChainContextError(f"missing encounter detail: {edge.encounter_id}")
        _require_active_path_encounter(detail)
        if not detail.evidence:
            raise InvalidChainContextError(f"missing encounter evidence: {edge.encounter_id}")
        encounters.append(_encounter_input(detail))
    return ChainExplanationPromptInput(
        source_person_id=result.source_person_id,
        target_person_id=result.target_person_id,
        max_depth=result.max_depth,
        language=language,
        people=people,
        encounters=encounters,
        retrieval_context=retrieval_context or [],
        retrieval_context_status=retrieval_context_status,
    )


def _require_active_path_encounter(detail: EncounterDetail) -> None:
    if (
        detail.status != EncounterStatus.ACTIVE.value
        or not detail.path_eligible
        or detail.certainty_level != CertaintyLevel.HIGH.value
        or detail.encounter_kind != EncounterKind.DIRECT_INTERACTION.value
    ):
        raise InvalidChainContextError(
            f"not an active path encounter: {detail.encounter_id}"
        )


def _encounter_input(detail: EncounterDetail) -> ChainExplanationEncounterInput:
    return ChainExplanationEncounterInput(
        encounter_id=str(detail.encounter_id),
        encounter_kind=detail.encounter_kind,
        certainty_level=detail.certainty_level,
        path_eligible=detail.path_eligible,
        evidence_summary=detail.evidence_summary,
        review_note=detail.review_note,
        source_work_id=detail.source_work_id,
        pages=detail.pages,
        evidence=[
            ChainExplanationEvidenceInput(
                evidence_id=evidence.evidence_id,
                candidate_table=evidence.candidate_table,
                candidate_id=evidence.candidate_id,
                source_ref_id=evidence.source_ref_id,
                source_work_id=evidence.source_work_id,
                pages=evidence.pages,
                evidence_kind=evidence.evidence_kind,
                evidence_summary=evidence.evidence_summary,
            )
            for evidence in detail.evidence
        ],
        source_refs=[
            ChainExplanationSourceRefInput(
                source_ref_id=source_ref.source_ref_id,
                source_work_id=source_ref.source_work_id,
                title_zh=source_ref.title_zh,
                title_en=source_ref.title_en,
                pages=source_ref.pages,
                notes=source_ref.notes,
            )
            for source_ref in detail.source_refs
        ],
    )
