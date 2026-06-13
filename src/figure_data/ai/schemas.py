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
