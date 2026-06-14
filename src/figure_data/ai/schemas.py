from typing import Literal

from pydantic import BaseModel, Field


class AIFoundationDiagnosticOutput(BaseModel):
    message: str = Field(min_length=1)
    echo_id: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


class CandidateReviewSuggestionOutput(BaseModel):
    suggested_action: Literal[
        "promote_candidate",
        "needs_human_review",
        "reject_duplicate",
        "insufficient_evidence",
        "not_path_candidate",
    ]
    priority_score: int = Field(ge=0, le=100)
    evidence_summary_draft: str = Field(min_length=1, max_length=2000)
    risk_flags: list[str] = Field(default_factory=list, max_length=20)
    supporting_source_ref_ids: list[int] = Field(default_factory=list, max_length=50)
    review_questions: list[str] = Field(default_factory=list, max_length=20)
    explanation: str = Field(min_length=1, max_length=2000)
    retrieval_source_ref_ids: list[int] = Field(default_factory=list, max_length=50)
    retrieval_document_ids: list[str] = Field(default_factory=list, max_length=50)
    retrieval_limitations: list[str] = Field(default_factory=list, max_length=20)


class ChainEdgeExplanationOutput(BaseModel):
    encounter_id: str = Field(min_length=1)
    explanation: str = Field(min_length=1, max_length=2000)
    evidence_basis: Literal["encounter_evidence", "source_ref", "structured_candidate"]
    source_ref_ids: list[int] = Field(default_factory=list, max_length=50)


class ChainExplanationOutput(BaseModel):
    summary: str = Field(min_length=1, max_length=3000)
    edge_explanations: list[ChainEdgeExplanationOutput] = Field(min_length=1, max_length=30)
    source_notes: list[str] = Field(default_factory=list, max_length=50)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    display_language: Literal["zh-Hans", "zh-Hant", "en"] = "zh-Hans"
    retrieval_document_ids: list[str] = Field(default_factory=list, max_length=50)
    retrieval_notes: list[str] = Field(default_factory=list, max_length=50)


class NoPathReviewTargetOutput(BaseModel):
    target_type: Literal[
        "candidate",
        "source_ref",
        "retrieval_document",
        "endpoint_neighbor",
    ]
    candidate_kind: Literal["relationship", "kinship"] | None = None
    candidate_id: int | None = Field(default=None, ge=1)
    source_ref_id: int | None = Field(default=None, ge=1)
    retrieval_document_id: str | None = Field(default=None, min_length=1, max_length=80)
    person_id: str | None = Field(default=None, min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=1000)
    review_question: str = Field(min_length=1, max_length=1000)


class NoPathRetrievalContextOutput(BaseModel):
    retrieval_document_id: str = Field(min_length=1, max_length=80)
    source_kind: str = Field(min_length=1, max_length=80)
    source_ref_id: int | None = Field(default=None, ge=1)
    score: float = Field(ge=-1.0, le=1.0)
    note: str = Field(min_length=1, max_length=1000)


class NoPathExplorationOutput(BaseModel):
    summary: str = Field(min_length=1, max_length=3000)
    likely_reasons: list[str] = Field(default_factory=list, max_length=20)
    suggested_review_targets: list[NoPathReviewTargetOutput] = Field(
        default_factory=list,
        max_length=20,
    )
    retrieval_context: list[NoPathRetrievalContextOutput] = Field(
        default_factory=list,
        max_length=20,
    )
    limitations: list[str] = Field(default_factory=list, max_length=20)
    display_language: Literal["zh-Hans", "zh-Hant", "en"] = "zh-Hans"
