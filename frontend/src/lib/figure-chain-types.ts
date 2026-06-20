export type ErrorBody = {
  code: string;
  message: string;
  details: Record<string, unknown>;
};

export type ErrorResponse = {
  error: ErrorBody;
};

export type PersonSearchItem = {
  person_id: string;
  display_name: string;
  primary_name_zh_hant: string | null;
  primary_name_zh_hans: string | null;
  primary_name_romanized: string | null;
  birth_year: number | null;
  death_year: number | null;
  index_year: number | null;
  dynasty_code: number | null;
  matching_aliases: string[];
  external_ids: string[];
};

export type PeopleSearchResponse = {
  query: string;
  limit: number;
  items: PersonSearchItem[];
};

export type PersonAlias = {
  alias_zh_hant: string | null;
  alias_zh_hans: string | null;
  alias_romanized: string | null;
  alias_type_label_zh: string | null;
  alias_type_label_en: string | null;
};

export type PersonExternalIdDetail = {
  source_name: string;
  external_id: string;
};

export type PersonEncounterSummaryCounts = {
  active_count: number;
  path_eligible_count: number;
  high_certainty_count: number;
};

export type PersonDetail = {
  person_id: string;
  display_name: string;
  primary_name_zh_hant: string | null;
  primary_name_zh_hans: string | null;
  primary_name_romanized: string | null;
  birth_year: number | null;
  death_year: number | null;
  index_year: number | null;
  floruit_start_year: number | null;
  floruit_end_year: number | null;
  dynasty_code: number | null;
  dynasty_label_zh: string | null;
  dynasty_label_en: string | null;
  is_female: boolean | null;
  notes: string | null;
  aliases: PersonAlias[];
  external_ids: PersonExternalIdDetail[];
  encounter_summary: PersonEncounterSummaryCounts;
};

export type PersonEncounterListItem = {
  encounter_id: string;
  other_person_id: string;
  other_person_name: string | null;
  other_person_birth_year: number | null;
  other_person_death_year: number | null;
  encounter_kind: string;
  certainty_level: string;
  path_eligible: boolean;
  source_work_id: number | null;
  source_title: string | null;
  pages: string | null;
  evidence_summary: string;
  status: string;
  reviewed_by: string;
  reviewed_at: string;
};

export type PersonEncounterListResponse = {
  items: PersonEncounterListItem[];
  count: number;
  limit: number;
  offset: number;
};

export type SourceWorkDetail = {
  source_work_id: number;
  text_code: number | null;
  title_zh: string | null;
  title_en: string | null;
  source_name: string;
  source_table: string;
  source_pk: string;
  ref_count: number;
  encounter_count: number;
};

export type LinkedEncounterEvidence = {
  evidence_id: number;
  encounter_id: string;
  evidence_kind: string;
  evidence_summary: string;
  pages: string | null;
  created_at: string;
};

export type SourceRefDetail = {
  source_ref_id: number;
  source_work: SourceWorkDetail | null;
  ref_source_table: string;
  ref_source_pk: string;
  pages: string | null;
  notes: string | null;
  source_name: string;
  source_table: string;
  source_pk: string;
  linked_encounter_evidence: LinkedEncounterEvidence[];
};

export type ChainEndpointRequest = {
  person_id?: string;
  cbdb_id?: string;
  query?: string;
};

export type ShortestChainRequest = {
  source: ChainEndpointRequest;
  target: ChainEndpointRequest;
  max_depth: number;
};

export type MultiPathFilters = {
  min_certainty_level: "high" | "medium" | "low" | null;
  encounter_kinds: string[];
  exclude_person_ids: string[];
  exclude_encounter_ids: string[];
  source_work_ids: number[];
  intermediate_dynasty_codes: number[];
  intermediate_year_min: number | null;
  intermediate_year_max: number | null;
};

export type MultiPathChainRequest = {
  source: ChainEndpointRequest;
  target: ChainEndpointRequest;
  max_depth: number;
  max_paths: number;
  extra_depth: number;
  filters: MultiPathFilters;
};

export type ChainPerson = {
  person_id: string;
  display_name: string;
  birth_year: number | null;
  death_year: number | null;
  cbdb_external_id: string | null;
};

export type ChainEdge = {
  encounter_id: string;
  encounter_kind: string;
  certainty_level: string;
  pages: string | null;
  evidence_summary: string;
};

export type ChainPath = {
  length: number;
  people: ChainPerson[];
  edges: ChainEdge[];
};

export type MultiPathItem = {
  path_id: string;
  rank: number;
  chain_hash: string;
  length: number;
  quality_score: number;
  people: ChainPerson[];
  edges: ChainEdge[];
};

export type AIChainEdgeExplanation = {
  encounter_id: string;
  explanation: string;
  evidence_basis: string;
  source_ref_ids: number[];
};

export type AIChainExplanation = {
  id: string;
  ai_run_id: string;
  chain_hash: string;
  source_person_id: string;
  target_person_id: string;
  max_depth: number;
  encounter_ids: string[];
  language: string;
  summary: string;
  edge_explanations: AIChainEdgeExplanation[];
  source_ref_ids: number[];
  status: string;
  created_at: string;
};

export type AIRun = {
  run_id: string;
  purpose: string;
  provider: string;
  model_name: string;
  prompt_key: string | null;
  prompt_version: string | null;
  status: string;
  schema_valid: boolean;
  error_code: string | null;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
  created_by: string;
};

export type AiJobCreateRequest = {
  job_type: string;
  target_type: string;
  target_kind: string;
  target_id: number;
  created_by: string;
  params: Record<string, unknown>;
};

export type AiJobResponse = {
  id: string;
  job_type: string;
  target_type: string;
  target_kind: string;
  target_id: number;
  status: string;
  created_by: string;
  params: Record<string, unknown>;
  result_ref_type: string | null;
  result_ref_id: string | null;
  error_code: string | null;
  error_message: string | null;
  queue_backend: string;
  queue_name: string | null;
  queue_job_id: string | null;
  enqueued_at: string | null;
  attempt_count: number;
  max_attempts: number;
  next_run_at: string | null;
  cancel_requested_at: string | null;
  worker_id: string | null;
  heartbeat_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AiJobCancelRequest = {
  cancelled_by: string;
};

export type AiJobRetryRequest = {
  created_by: string;
};

export type AiJobEvent = {
  id: string;
  job_id: string;
  event_type: string;
  actor: string;
  message: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type AiJobEventListResponse = {
  items: AiJobEvent[];
  count: number;
};

export type AiJobHealthResponse = {
  status_counts: Record<string, number>;
  queued_count: number;
  running_count: number;
  succeeded_count: number;
  failed_count: number;
  cancelled_count: number;
  stale_running_count: number;
  oldest_queued_at: string | null;
};

export type AiJobListResponse = {
  items: AiJobResponse[];
  count: number;
  limit: number;
};

export type ShortestChainResponse = {
  status: "found" | "no_path";
  source_person_id: string;
  target_person_id: string;
  max_depth: number;
  chain_hash: string | null;
  path: ChainPath | null;
};

export type MultiPathChainResponse = {
  status: "found" | "no_path";
  source_person_id: string;
  target_person_id: string;
  max_depth: number;
  max_paths: number;
  extra_depth: number;
  shortest_length: number | null;
  returned_paths: number;
  paths: MultiPathItem[];
  filters_applied: MultiPathFilters;
};

export type ChainShareCreateRequest = {
  source_person_id: string;
  target_person_id: string;
  chain_hash: string;
  path_payload: Record<string, unknown>;
  filters_applied: Record<string, unknown>;
  include_ai_explanation: boolean;
  include_rag_context: boolean;
  created_by: string | null;
};

export type ChainShareCreateResponse = {
  share_slug: string;
  url_path: string;
};

export type ChainShareDetail = {
  id: string;
  share_slug: string;
  url_path: string;
  source_person_id: string;
  target_person_id: string;
  chain_hash: string;
  encounter_ids: string[];
  path_payload: Record<string, unknown>;
  filters_applied: Record<string, unknown>;
  include_ai_explanation: boolean;
  include_rag_context: boolean;
  schema_version: string;
  created_by: string | null;
  created_at: string;
};

export type MarkdownExportRequest = {
  share_slug: string;
  format: string;
};

export type MarkdownExportResponse = {
  content: string;
  filename: string;
  source_ids: Record<string, string[]>;
};

export type EncounterPerson = {
  person_id: string;
  cbdb_id: number | null;
  display_name: string;
  primary_name_zh_hant: string | null;
  primary_name_zh_hans: string | null;
  primary_name_romanized: string | null;
  birth_year: number | null;
  death_year: number | null;
  external_ids: string[];
};

export type EncounterEvidence = {
  evidence_id: number;
  candidate_table: string | null;
  candidate_id: number | null;
  source_ref_id: number | null;
  source_work_id: number | null;
  pages: string | null;
  evidence_kind: string;
  evidence_summary: string;
  created_at: string;
};

export type SourceRef = {
  source_ref_id: number;
  source_work_id: number | null;
  title_zh: string | null;
  title_en: string | null;
  pages: string | null;
  notes: string | null;
};

export type EncounterDetail = {
  encounter_id: string;
  status: string;
  encounter_kind: string;
  certainty_level: string;
  path_eligible: boolean;
  source_work_id: number | null;
  pages: string | null;
  evidence_summary: string;
  review_note: string | null;
  reviewed_by: string;
  reviewed_at: string;
  person_a: EncounterPerson;
  person_b: EncounterPerson;
  evidence: EncounterEvidence[];
  source_refs: SourceRef[];
};

export type ReviewCandidatePerson = {
  person_id: string | null;
  cbdb_id: number | null;
  display_name: string;
  primary_name_zh_hant: string | null;
  primary_name_zh_hans: string | null;
  primary_name_romanized: string | null;
  birth_year: number | null;
  death_year: number | null;
};

export type ReviewPromotionReadiness = {
  default_promotable: boolean;
  default_path_eligible: boolean;
  reasons: string[];
};

export type ReviewCandidateSummary = {
  kind: string;
  candidate_id: number;
  person_a: ReviewCandidatePerson;
  person_b: ReviewCandidatePerson;
  relation_type: string | null;
  time_summary: string | null;
  place_summary: string | null;
  status: string;
  confidence: number;
  evidence_count: number;
  source_count: number;
  promotion_readiness: ReviewPromotionReadiness;
  latest_ai_job_status: string | null;
  has_ai_suggestion: boolean;
};

export type ReviewCandidateListResponse = {
  items: ReviewCandidateSummary[];
  limit: number;
  offset: number;
  count: number;
};

export type ReviewCandidateRelation = {
  relation_type: string | null;
  basis: string | null;
  strength: string | null;
  notes: string | null;
  source_name: string | null;
  source_table: string | null;
  source_pk: string | null;
};

export type ReviewCandidateTime = {
  summary: string | null;
  pages: string | null;
};

export type ReviewCandidatePlace = {
  summary: string | null;
};

export type ReviewSourceRef = {
  source_ref_id: number;
  source_work_id: number | null;
  title_zh: string | null;
  title_en: string | null;
  pages: string | null;
  notes: string | null;
};

export type ReviewCandidateEvidence = {
  evidence_id: number | null;
  source_ref_id: number | null;
  evidence_kind: string;
  evidence_summary: string;
  pages: string | null;
};

export type ReviewLinkedEncounter = {
  encounter_id: string;
  status: string | null;
};

export type ReviewAiSuggestionSummary = {
  suggestion_id: string | null;
  ai_run_id: string | null;
  status: string;
  recommendation: string | null;
  summary: string | null;
  created_at: string | null;
};

export type ReviewAiJobSummary = {
  run_id: string;
  status: string;
  purpose: string;
  created_at: string | null;
  finished_at: string | null;
};

export type ReviewCandidateDetail = {
  kind: string;
  candidate_id: number;
  person_a: ReviewCandidatePerson;
  person_b: ReviewCandidatePerson;
  relation: ReviewCandidateRelation;
  time: ReviewCandidateTime | null;
  place: ReviewCandidatePlace | null;
  status: string;
  confidence: number;
  source_refs: ReviewSourceRef[];
  evidence: ReviewCandidateEvidence[];
  promotion_readiness: ReviewPromotionReadiness;
  linked_encounter: ReviewLinkedEncounter | null;
  latest_ai_suggestion: ReviewAiSuggestionSummary | null;
  ai_jobs: ReviewAiJobSummary[];
};

export type ReviewActionRequest = {
  reviewed_by: string;
  evidence_summary?: string;
  note?: string | null;
  allow_non_default?: boolean;
  reason?: string;
};

export type ReviewActionResponse = {
  kind: string;
  candidate_id: number;
  status: string;
  reviewed_by: string;
  encounter: ReviewLinkedEncounter | null;
  message: string | null;
};

export type DependencyStatus = {
  status: "ok" | "error";
  message?: string | null;
};

export type ReadyResponse = {
  status: "ready" | "not_ready";
  dependencies: Record<string, DependencyStatus>;
};

export type AdminOperationDetail = {
  operation_id: string;
  operation_type: string;
  actor: string;
  status: string;
  request_payload: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  error_message: string | null;
  related_resource_type: string | null;
  related_resource_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AdminOperationListResponse = {
  items: AdminOperationDetail[];
  limit: number;
  offset: number;
  count: number;
};

export type AdminResourceColumn = {
  key: string;
  label: string;
  type: string;
  operators: string[];
  selectable: boolean;
  filterable: boolean;
  sortable: boolean;
  default_selected: boolean;
  link: string | null;
};

export type AdminResource = {
  name: string;
  label: string;
  primary_key: string;
  default_order_by: string;
  default_order_direction: "asc" | "desc";
  columns: AdminResourceColumn[];
};

export type AdminResourceListResponse = {
  resources: AdminResource[];
};

export type AdminResourceFilterRequest = {
  field: string;
  operator: string;
  value: unknown;
};

export type AdminResourceQueryRequest = {
  resource: string;
  select: string[];
  filters: AdminResourceFilterRequest[];
  order_by: string | null;
  order_direction: "asc" | "desc";
  limit: number;
  offset: number;
};

export type AdminResourceQueryResponse = {
  resource: string;
  columns: AdminResourceColumn[];
  rows: Record<string, unknown>[];
  limit: number;
  offset: number;
  preview: string;
};

export type AdminGraphBatchSummary = {
  id: string;
  mode: string;
  status: string;
  triggered_by: string;
  source_watermark: string | null;
  encounters_seen: number;
  relationships_written: number;
  relationships_deleted: number;
  persons_written: number;
  validation_status: string;
  validation_summary: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
};

export type AdminGraphStatusResponse = {
  latest_success: AdminGraphBatchSummary | null;
  latest_failed: AdminGraphBatchSummary | null;
  active_encounter_count: number;
  path_eligible_encounter_count: number;
  stale_running_operations: AdminOperationDetail[];
};

export type AdminGraphOperationResponse = {
  operation_id: string;
  operation_type: string;
  status: string;
  preview: string;
};
