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


class PersonAliasResponse(BaseModel):
    alias_zh_hant: str | None
    alias_zh_hans: str | None
    alias_romanized: str | None
    alias_type_label_zh: str | None
    alias_type_label_en: str | None


class PersonExternalIdResponse(BaseModel):
    source_name: str
    external_id: str


class PersonEncounterSummaryCountsResponse(BaseModel):
    active_count: int
    path_eligible_count: int
    high_certainty_count: int


class PersonDetailResponse(BaseModel):
    person_id: UUID
    display_name: str
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    index_year: int | None
    floruit_start_year: int | None
    floruit_end_year: int | None
    dynasty_code: int | None
    dynasty_label_zh: str | None
    dynasty_label_en: str | None
    is_female: bool | None
    notes: str | None
    aliases: list[PersonAliasResponse]
    external_ids: list[PersonExternalIdResponse]
    encounter_summary: PersonEncounterSummaryCountsResponse


class PersonEncounterListItemResponse(BaseModel):
    encounter_id: UUID
    other_person_id: UUID
    other_person_name: str | None
    other_person_birth_year: int | None
    other_person_death_year: int | None
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    source_work_id: int | None
    source_title: str | None
    pages: str | None
    evidence_summary: str
    status: str
    reviewed_by: str
    reviewed_at: datetime


class PersonEncounterListResponse(BaseModel):
    items: list[PersonEncounterListItemResponse]
    count: int
    limit: int
    offset: int


class SourceWorkDetailResponse(BaseModel):
    source_work_id: int
    text_code: int | None
    title_zh: str | None
    title_en: str | None
    source_name: str
    source_table: str
    source_pk: str
    ref_count: int
    encounter_count: int


class LinkedEncounterEvidenceResponse(BaseModel):
    evidence_id: int
    encounter_id: UUID
    evidence_kind: str
    evidence_summary: str
    pages: str | None
    created_at: datetime


class SourceRefDetailResponse(BaseModel):
    source_ref_id: int
    source_work: SourceWorkDetailResponse | None
    ref_source_table: str
    ref_source_pk: str
    pages: str | None
    notes: str | None
    source_name: str
    source_table: str
    source_pk: str
    linked_encounter_evidence: list[LinkedEncounterEvidenceResponse]


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


class MultiPathFiltersRequest(BaseModel):
    min_certainty_level: Literal["high", "medium", "low"] | None = "high"
    encounter_kinds: list[str] = Field(default_factory=list)
    exclude_person_ids: list[UUID] = Field(default_factory=list)
    exclude_encounter_ids: list[UUID] = Field(default_factory=list)
    source_work_ids: list[int] = Field(default_factory=list)
    intermediate_dynasty_codes: list[int] = Field(default_factory=list)
    intermediate_year_min: int | None = None
    intermediate_year_max: int | None = None


class MultiPathChainRequest(BaseModel):
    source: ChainEndpointRequest
    target: ChainEndpointRequest
    max_depth: int = Field(default=12, ge=1, le=20)
    max_paths: int = Field(default=5, ge=1, le=20)
    extra_depth: int = Field(default=0, ge=0, le=2)
    filters: MultiPathFiltersRequest = Field(default_factory=MultiPathFiltersRequest)


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


class MultiPathItemResponse(BaseModel):
    path_id: str
    rank: int
    chain_hash: str
    length: int
    quality_score: float
    people: list[ChainPersonResponse]
    edges: list[ChainEdgeResponse]


class ShortestChainResponse(BaseModel):
    status: Literal["found", "no_path"]
    source_person_id: str
    target_person_id: str
    max_depth: int
    chain_hash: str | None = None
    path: ChainPathResponse | None


class MultiPathChainResponse(BaseModel):
    status: Literal["found", "no_path"]
    source_person_id: str
    target_person_id: str
    max_depth: int
    max_paths: int
    extra_depth: int
    shortest_length: int | None
    returned_paths: int
    paths: list[MultiPathItemResponse]
    filters_applied: MultiPathFiltersRequest


class ChainShareCreateRequest(BaseModel):
    source_person_id: UUID
    target_person_id: UUID
    chain_hash: str = Field(min_length=1)
    path_payload: dict[str, object]
    filters_applied: dict[str, object] = Field(default_factory=dict)
    include_ai_explanation: bool = False
    include_rag_context: bool = False
    created_by: str | None = None


class ChainShareCreateResponse(BaseModel):
    share_slug: str
    url_path: str


class ChainShareDetailResponse(BaseModel):
    id: UUID
    share_slug: str
    url_path: str
    source_person_id: UUID
    target_person_id: UUID
    chain_hash: str
    encounter_ids: list[str]
    path_payload: dict[str, object]
    filters_applied: dict[str, object]
    include_ai_explanation: bool
    include_rag_context: bool
    schema_version: str
    created_by: str | None
    created_at: datetime


class MarkdownExportRequest(BaseModel):
    share_slug: str = Field(min_length=1)
    format: str = "markdown"


class MarkdownExportResponse(BaseModel):
    content: str
    filename: str
    source_ids: dict[str, list[str]]


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


class AiJobCreateRequest(BaseModel):
    job_type: str
    target_type: str
    target_kind: str
    target_id: int = Field(ge=1)
    created_by: str = Field(min_length=1)
    params: dict[str, object] = Field(default_factory=dict)


class AiJobCancelRequest(BaseModel):
    cancelled_by: str = Field(min_length=1)


class AiJobRetryRequest(BaseModel):
    created_by: str = Field(min_length=1)


class AiJobResponse(BaseModel):
    id: UUID
    job_type: str
    target_type: str
    target_kind: str
    target_id: int
    status: str
    created_by: str
    params: dict[str, object]
    result_ref_type: str | None
    result_ref_id: UUID | None
    error_code: str | None
    error_message: str | None
    queue_backend: str
    queue_name: str | None
    queue_job_id: str | None
    enqueued_at: datetime | None
    attempt_count: int
    max_attempts: int
    next_run_at: datetime | None
    cancel_requested_at: datetime | None
    worker_id: str | None
    heartbeat_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AiJobListResponse(BaseModel):
    items: list[AiJobResponse]
    count: int
    limit: int


class AiJobEventResponse(BaseModel):
    id: UUID
    job_id: UUID
    event_type: str
    actor: str
    message: str | None
    metadata: dict[str, object]
    created_at: datetime


class AiJobEventListResponse(BaseModel):
    items: list[AiJobEventResponse]
    count: int


class AiJobHealthResponse(BaseModel):
    status_counts: dict[str, int]
    queued_count: int
    running_count: int
    succeeded_count: int
    failed_count: int
    cancelled_count: int
    stale_running_count: int
    oldest_queued_at: datetime | None


class AdminAIJobListResponse(BaseModel):
    items: list[AiJobResponse]
    count: int
    limit: int
    offset: int


class AdminAIJobActionRequest(BaseModel):
    actor: str = Field(default="local", min_length=1, max_length=128)


class AdminAIJobsRequeueRequest(AdminAIJobActionRequest):
    limit: int = Field(default=50, ge=1, le=200)


class AdminAIJobActionResponse(BaseModel):
    operation_id: UUID
    operation_type: str
    status: str
    job: AiJobResponse | None = None
    result_summary: dict[str, object] = Field(default_factory=dict)
    preview: str


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


class ReviewPromoteRequest(BaseModel):
    reviewed_by: str = Field(min_length=1)
    evidence_summary: str = Field(min_length=1)
    note: str | None = None
    allow_non_default: bool = False


class ReviewRejectRequest(BaseModel):
    reviewed_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ReviewNeedsReviewRequest(BaseModel):
    reviewed_by: str = Field(min_length=1)
    note: str | None = None


class ReviewActionResponse(BaseModel):
    kind: str
    candidate_id: int
    status: str
    reviewed_by: str
    encounter: ReviewLinkedEncounterResponse | None
    message: str | None


class AdminReviewActionResponse(BaseModel):
    operation_id: UUID
    operation_type: str
    status: str
    action: ReviewActionResponse
    preview: str


class AdminEncounterRetractRequest(BaseModel):
    reviewed_by: str = Field(min_length=1)
    note: str = Field(min_length=1)
    force: bool = False


class AdminEncounterRetractResultResponse(BaseModel):
    encounter_id: UUID
    status: str
    path_eligible: bool
    linked_candidates_updated: int


class AdminEncounterRetractResponse(BaseModel):
    operation_id: UUID
    operation_type: str
    status: str
    result: AdminEncounterRetractResultResponse
    preview: str


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


class SystemDependencyStatusResponse(BaseModel):
    status: str
    message: str | None = None


class SystemDiagnosticsResponse(BaseModel):
    status: str
    dependencies: dict[str, SystemDependencyStatusResponse]
    config: dict[str, object]


class AdminOperationDetailResponse(BaseModel):
    operation_id: UUID
    operation_type: str
    actor: str
    status: str
    request_payload: dict[str, object]
    result_summary: dict[str, object]
    error_message: str | None
    related_resource_type: str | None
    related_resource_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminOperationListResponse(BaseModel):
    items: list[AdminOperationDetailResponse]
    limit: int
    offset: int
    count: int


class AdminResourceColumnResponse(BaseModel):
    key: str
    label: str
    type: str
    operators: list[str]
    selectable: bool
    filterable: bool
    sortable: bool
    default_selected: bool
    link: str | None


class AdminResourceResponse(BaseModel):
    name: str
    label: str
    primary_key: str
    default_order_by: str
    default_order_direction: str
    columns: list[AdminResourceColumnResponse]


class AdminResourceListResponse(BaseModel):
    resources: list[AdminResourceResponse]


class AdminResourceFilterRequest(BaseModel):
    field: str
    operator: str
    value: object | None = None


class AdminResourceQueryRequest(BaseModel):
    resource: str
    select: list[str] = Field(default_factory=list)
    filters: list[AdminResourceFilterRequest] = Field(default_factory=list)
    order_by: str | None = None
    order_direction: Literal["asc", "desc"] = "asc"
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class AdminResourceQueryResponse(BaseModel):
    resource: str
    columns: list[AdminResourceColumnResponse]
    rows: list[dict[str, object]]
    limit: int
    offset: int
    preview: str


class AdminGraphBatchSummaryResponse(BaseModel):
    id: str
    mode: str
    status: str
    triggered_by: str
    source_watermark: datetime | None
    encounters_seen: int
    relationships_written: int
    relationships_deleted: int
    persons_written: int
    validation_status: str
    validation_summary: dict[str, object]
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class AdminGraphStatusResponse(BaseModel):
    latest_success: AdminGraphBatchSummaryResponse | None
    latest_failed: AdminGraphBatchSummaryResponse | None
    active_encounter_count: int
    path_eligible_encounter_count: int
    stale_running_operations: list[AdminOperationDetailResponse]


class AdminGraphOperationRequest(BaseModel):
    actor: str = Field(default="local", min_length=1, max_length=128)


class AdminGraphSyncRequest(AdminGraphOperationRequest):
    mode: Literal["rebuild", "incremental"]


class AdminGraphOperationResponse(BaseModel):
    operation_id: UUID
    operation_type: str
    status: str
    preview: str
