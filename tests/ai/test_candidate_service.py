from uuid import UUID

from figure_data.ai.candidate_repository import (
    CandidateSuggestionRecord,
    NewCandidateReviewSuggestion,
)
from figure_data.ai.candidate_service import save_candidate_review_suggestion_output
from figure_data.ai.schemas import CandidateReviewSuggestionOutput
from figure_data.review.types import CandidateKind


class FakeRepository:
    def __init__(self) -> None:
        self.created: list[NewCandidateReviewSuggestion] = []
        self.suggestion_id = UUID("00000000-0000-0000-0000-000000000201")

    def create(self, session: object, suggestion: NewCandidateReviewSuggestion) -> UUID:
        self.created.append(suggestion)
        return self.suggestion_id

    def get(self, session: object, suggestion_id: UUID) -> CandidateSuggestionRecord:
        created = self.created[0]
        return CandidateSuggestionRecord(
            id=suggestion_id,
            ai_run_id=created.ai_run_id,
            candidate_kind=created.candidate_kind,
            candidate_id=created.candidate_id,
            suggested_action=created.suggested_action,
            priority_score=created.priority_score,
            evidence_summary_draft=created.evidence_summary_draft,
            risk_flags=created.risk_flags,
            supporting_source_ref_ids=created.supporting_source_ref_ids,
            review_questions=created.review_questions,
            explanation=created.explanation,
            status="generated",
            reviewed_by=None,
            reviewed_at=None,
            review_note=None,
            created_at="2026-06-13T00:00:00+00:00",
        )


def test_save_candidate_review_suggestion_output_writes_ai_table_only() -> None:
    repository = FakeRepository()
    output = CandidateReviewSuggestionOutput.model_validate(
        {
            "suggested_action": "needs_human_review",
            "priority_score": 80,
            "evidence_summary_draft": "结构化关系显示二人可能有互动。",
            "risk_flags": ["source_text_missing"],
            "supporting_source_ref_ids": [501],
            "review_questions": ["是否有原文？"],
            "explanation": "只基于输入材料。",
        }
    )

    record = save_candidate_review_suggestion_output(
        session=object(),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        output=output,
        repository=repository,
    )

    assert record.id == repository.suggestion_id
    assert repository.created[0].candidate_kind is CandidateKind.RELATIONSHIP
    assert repository.created[0].candidate_id == 960698
    assert repository.created[0].suggested_action == "needs_human_review"
