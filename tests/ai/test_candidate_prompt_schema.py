from pydantic import ValidationError
from pytest import raises

from figure_data.ai.prompts import get_prompt_definition
from figure_data.ai.schemas import CandidateReviewSuggestionOutput


def test_candidate_review_prompt_is_registered() -> None:
    prompt = get_prompt_definition("candidate_review_suggestion")

    assert prompt.prompt_key == "candidate_review_suggestion"
    assert prompt.purpose == "candidate_review_suggestion"
    assert prompt.output_schema_name == "candidate_review_suggestion_output"
    assert prompt.output_schema_version == "1"
    assert "{candidate_json}" in prompt.user_prompt_template
    assert "不得自动提升" in prompt.system_prompt


def test_candidate_review_suggestion_output_accepts_valid_payload() -> None:
    output = CandidateReviewSuggestionOutput.model_validate(
        {
            "suggested_action": "needs_human_review",
            "priority_score": 72,
            "evidence_summary_draft": (
                "结构化关系显示二人可能有直接互动，需要审核原始来源。"
            ),
            "risk_flags": ["source_text_missing"],
            "supporting_source_ref_ids": [101, 102],
            "review_questions": ["是否能找到原书页码对应文字？"],
            "explanation": "该建议只基于输入的候选关系和 source_ref 信息。",
        }
    )

    assert output.suggested_action == "needs_human_review"
    assert output.priority_score == 72
    assert output.supporting_source_ref_ids == [101, 102]


def test_candidate_review_suggestion_output_rejects_invalid_action() -> None:
    with raises(ValidationError):
        CandidateReviewSuggestionOutput.model_validate(
            {
                "suggested_action": "promote_encounter_now",
                "priority_score": 72,
                "evidence_summary_draft": "结构化关系显示二人可能有直接互动。",
                "risk_flags": [],
                "supporting_source_ref_ids": [],
                "review_questions": [],
                "explanation": "该建议只基于输入。",
            }
        )
