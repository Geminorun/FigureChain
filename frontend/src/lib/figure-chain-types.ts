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

export type ShortestChainResponse = {
  status: "found" | "no_path";
  source_person_id: string;
  target_person_id: string;
  max_depth: number;
  chain_hash: string | null;
  path: ChainPath | null;
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

export type DependencyStatus = {
  status: "ok" | "error";
  message?: string | null;
};

export type ReadyResponse = {
  status: "ready" | "not_ready";
  dependencies: Record<string, DependencyStatus>;
};
