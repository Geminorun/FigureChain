from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


def display_name(
    primary_name_zh_hant: str | None,
    primary_name_zh_hans: str | None,
    primary_name_romanized: str | None,
    person_id: str,
) -> str:
    return primary_name_zh_hant or primary_name_zh_hans or primary_name_romanized or person_id


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class PersonSearchItem(BaseModel):
    person_id: str
    display_name: str
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    index_year: int | None
    dynasty_code: int | None
    matching_aliases: list[str]
    external_ids: list[str]


class PeopleSearchResponse(BaseModel):
    query: str
    limit: int
    items: list[PersonSearchItem]


class ChainEndpointRequest(BaseModel):
    person_id: UUID | None = None
    cbdb_id: str | None = None
    query: str | None = None

    @model_validator(mode="after")
    def validate_exactly_one_locator(self) -> ChainEndpointRequest:
        locators = [
            self.person_id is not None,
            bool(self.cbdb_id and self.cbdb_id.strip()),
            bool(self.query and self.query.strip()),
        ]
        if sum(locators) != 1:
            raise ValueError("endpoint must provide exactly one locator")
        if self.cbdb_id is not None:
            self.cbdb_id = self.cbdb_id.strip()
        if self.query is not None:
            self.query = self.query.strip()
        return self


class ShortestChainRequest(BaseModel):
    source: ChainEndpointRequest
    target: ChainEndpointRequest
    max_depth: int = Field(default=12, ge=1, le=30)


class ChainPersonResponse(BaseModel):
    person_id: str
    display_name: str
    birth_year: int | None
    death_year: int | None
    cbdb_external_id: str | None


class ChainEdgeResponse(BaseModel):
    encounter_id: str
    encounter_kind: str
    certainty_level: str
    pages: str | None
    evidence_summary: str


class ChainPathResponse(BaseModel):
    length: int
    people: list[ChainPersonResponse]
    edges: list[ChainEdgeResponse]


class ShortestChainResponse(BaseModel):
    status: Literal["found", "no_path"]
    source_person_id: str
    target_person_id: str
    max_depth: int
    chain_hash: str | None = None
    path: ChainPathResponse | None


class AIChainExplanationResponse(BaseModel):
    id: UUID
    ai_run_id: UUID
    chain_hash: str
    source_person_id: UUID
    target_person_id: UUID
    max_depth: int
    encounter_ids: list[str]
    language: str
    summary: str
    edge_explanations: list[dict[str, object]]
    source_ref_ids: list[int]
    status: str
    created_at: datetime


class AIRunResponse(BaseModel):
    run_id: UUID
    purpose: str
    provider: str
    model_name: str
    prompt_key: str | None
    prompt_version: str | None
    status: str
    schema_valid: bool
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    created_by: str


class EncounterPersonResponse(BaseModel):
    person_id: str
    cbdb_id: int | None
    display_name: str
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    external_ids: list[str]


class EncounterEvidenceResponse(BaseModel):
    evidence_id: int
    candidate_table: str | None
    candidate_id: int | None
    source_ref_id: int | None
    source_work_id: int | None
    pages: str | None
    evidence_kind: str
    evidence_summary: str
    created_at: datetime


class SourceRefResponse(BaseModel):
    source_ref_id: int
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    notes: str | None


class EncounterDetailResponse(BaseModel):
    encounter_id: UUID
    status: str
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    source_work_id: int | None
    pages: str | None
    evidence_summary: str
    review_note: str | None
    reviewed_by: str
    reviewed_at: datetime
    person_a: EncounterPersonResponse
    person_b: EncounterPersonResponse
    evidence: list[EncounterEvidenceResponse]
    source_refs: list[SourceRefResponse]


class ReviewCandidatePersonResponse(BaseModel):
    person_id: str | None
    cbdb_id: int | None
    display_name: str
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None


class ReviewPromotionReadinessResponse(BaseModel):
    default_promotable: bool
    default_path_eligible: bool
    reasons: list[str]


class ReviewCandidateSummary(BaseModel):
    kind: str
    candidate_id: int
    person_a: ReviewCandidatePersonResponse
    person_b: ReviewCandidatePersonResponse
    relation_type: str | None
    time_summary: str | None
    place_summary: str | None
    status: str
    confidence: float
    evidence_count: int
    source_count: int
    promotion_readiness: ReviewPromotionReadinessResponse
    latest_ai_job_status: str | None
    has_ai_suggestion: bool


class ReviewCandidateListResponse(BaseModel):
    items: list[ReviewCandidateSummary]
    limit: int
    offset: int
    count: int


class ReviewCandidateRelationResponse(BaseModel):
    relation_type: str | None
    basis: str | None
    strength: str | None
    notes: str | None
    source_name: str | None
    source_table: str | None
    source_pk: str | None


class ReviewCandidateTimeResponse(BaseModel):
    summary: str | None
    pages: str | None


class ReviewCandidatePlaceResponse(BaseModel):
    summary: str | None


class ReviewSourceRefResponse(BaseModel):
    source_ref_id: int
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    notes: str | None


class ReviewCandidateEvidenceResponse(BaseModel):
    evidence_id: int | None
    source_ref_id: int | None
    evidence_kind: str
    evidence_summary: str
    pages: str | None


class ReviewLinkedEncounterResponse(BaseModel):
    encounter_id: UUID
    status: str | None = None


class ReviewAiSuggestionSummary(BaseModel):
    suggestion_id: UUID | None
    ai_run_id: UUID | None
    status: str
    recommendation: str | None
    summary: str | None
    created_at: datetime | None


class ReviewAiJobSummary(BaseModel):
    run_id: UUID
    status: str
    purpose: str
    created_at: datetime | None
    finished_at: datetime | None


class ReviewCandidateDetailResponse(BaseModel):
    kind: str
    candidate_id: int
    person_a: ReviewCandidatePersonResponse
    person_b: ReviewCandidatePersonResponse
    relation: ReviewCandidateRelationResponse
    time: ReviewCandidateTimeResponse | None
    place: ReviewCandidatePlaceResponse | None
    status: str
    confidence: float
    source_refs: list[ReviewSourceRefResponse]
    evidence: list[ReviewCandidateEvidenceResponse]
    promotion_readiness: ReviewPromotionReadinessResponse
    linked_encounter: ReviewLinkedEncounterResponse | None
    latest_ai_suggestion: ReviewAiSuggestionSummary | None
    ai_jobs: list[ReviewAiJobSummary]


class DependencyStatusResponse(BaseModel):
    status: Literal["ok", "error"]
    message: str | None = None


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: dict[str, DependencyStatusResponse]
