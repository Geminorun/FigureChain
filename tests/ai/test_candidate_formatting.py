from uuid import UUID

from figure_data.ai.candidate_formatting import (
    format_candidate_suggestion_detail,
    format_candidate_suggestion_summaries,
)
from figure_data.ai.candidate_repository import CandidateSuggestionRecord
from figure_data.review.types import CandidateKind


def suggestion_record() -> CandidateSuggestionRecord:
    return CandidateSuggestionRecord(
        id=UUID("00000000-0000-0000-0000-000000000201"),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        suggested_action="needs_human_review",
        priority_score=80,
        evidence_summary_draft="结构化关系显示二人可能有互动。",
        risk_flags=["source_text_missing"],
        supporting_source_ref_ids=[501],
        review_questions=["是否有原文？"],
        explanation="只基于输入材料。",
        status="generated",
        reviewed_by=None,
        reviewed_at=None,
        review_note=None,
        created_at="2026-06-13T00:00:00+00:00",
    )


def test_format_candidate_suggestion_summaries_outputs_tsv() -> None:
    lines = format_candidate_suggestion_summaries([suggestion_record()])

    assert lines[0].startswith("id\tai_run_id\tcandidate_kind")
    assert "needs_human_review" in lines[1]
    assert "source_text_missing" in lines[1]


def test_format_candidate_suggestion_detail_outputs_trace_fields() -> None:
    lines = format_candidate_suggestion_detail(suggestion_record())

    assert "ai_candidate_suggestion\t00000000-0000-0000-0000-000000000201" in lines
    assert "ai_run\t00000000-0000-0000-0000-000000000301" in lines
    assert "candidate\trelationship\t960698" in lines
    assert "supporting_source_ref\t501" in lines
