from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvaluationCapability(StrEnum):
    CANDIDATE_REVIEW_SUGGESTION = "candidate_review_suggestion"
    CHAIN_EXPLANATION = "chain_explanation"
    RAG_SEARCH = "rag_search"
    NO_PATH_EXPLORATION = "no_path_exploration"


class EvaluationDimension(StrEnum):
    FAITHFULNESS = "faithfulness"
    TRACEABILITY = "traceability"
    SAFETY = "safety"
    USEFULNESS = "usefulness"
    CLARITY = "clarity"


class AcceptanceCommandStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_RUN = "not_run"


class EvaluationBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvaluationTraceIds(EvaluationBaseModel):
    source_ref_ids: list[int] = Field(default_factory=list)
    encounter_ids: list[str] = Field(default_factory=list)
    retrieval_document_ids: list[str] = Field(default_factory=list)
    candidate_keys: list[str] = Field(default_factory=list)


class EvaluationScore(EvaluationBaseModel):
    dimension: EvaluationDimension
    score: int = Field(ge=0, le=3)
    notes: str = ""


class EvaluationSample(EvaluationBaseModel):
    sample_id: str = Field(min_length=1)
    capability: EvaluationCapability
    title: str = Field(min_length=1)
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    output_snapshot: dict[str, Any] = Field(default_factory=dict)
    expected_trace_ids: EvaluationTraceIds = Field(default_factory=EvaluationTraceIds)
    forbidden_phrases: list[str] = Field(default_factory=list)
    manual_scores: dict[EvaluationDimension, EvaluationScore] = Field(default_factory=dict)
    notes: str = ""
    ai_run_id: UUID | None = None
    provider: str | None = None
    model_name: str | None = None
    prompt_key: str | None = None
    prompt_version: str | None = None
    retrieval_document_ids: list[str] = Field(default_factory=list)

    @field_validator("manual_scores")
    @classmethod
    def validate_manual_score_keys(
        cls,
        value: dict[EvaluationDimension, EvaluationScore],
    ) -> dict[EvaluationDimension, EvaluationScore]:
        for dimension, score in value.items():
            if score.dimension != dimension:
                raise ValueError("manual_scores keys must match score dimensions")
        return value


class EvaluationFixture(EvaluationBaseModel):
    fixture_version: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    samples: list[EvaluationSample]

    @model_validator(mode="after")
    def validate_unique_sample_ids(self) -> EvaluationFixture:
        sample_ids = [sample.sample_id for sample in self.samples]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("sample_id values must be unique")
        return self


class AcceptanceCommandEvidence(EvaluationBaseModel):
    command: str = Field(min_length=1)
    status: AcceptanceCommandStatus
    summary: str = ""
    output_excerpt: str = Field(default="", max_length=1000)


class Stage4AcceptanceEvidence(EvaluationBaseModel):
    evidence_version: str = Field(min_length=1)
    run_date: str = Field(min_length=1)
    git_branch: str = ""
    commit_sha: str = ""
    commands: list[AcceptanceCommandEvidence] = Field(default_factory=list)
    reviewer_notes: str = ""


class EvaluationItemResult(EvaluationBaseModel):
    sample_id: str
    capability: EvaluationCapability
    title: str
    scores: list[EvaluationScore]
    passed: bool
    findings: list[str] = Field(default_factory=list)
    ai_run_id: UUID | None = None
    provider: str | None = None
    model_name: str | None = None
    prompt_key: str | None = None
    prompt_version: str | None = None
    retrieval_document_ids: list[str] = Field(default_factory=list)


class EvaluationReport(EvaluationBaseModel):
    generated_at: str
    fixture_version: str
    item_results: list[EvaluationItemResult]
    acceptance_evidence: Stage4AcceptanceEvidence | None = None
    gate_summary: dict[str, Any]
    recommendation: str
