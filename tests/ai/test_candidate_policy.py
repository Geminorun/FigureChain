from pytest import raises

from figure_data.ai.candidate_policy import validate_candidate_review_suggestion_policy
from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.schemas import CandidateReviewSuggestionOutput


def suggestion_output(**overrides: object) -> CandidateReviewSuggestionOutput:
    payload = {
        "suggested_action": "needs_human_review",
        "priority_score": 50,
        "evidence_summary_draft": "结构化关系显示二人可能有互动，需要人工查证。",
        "risk_flags": ["source_text_missing"],
        "supporting_source_ref_ids": [101],
        "review_questions": ["是否有原文可支持见面？"],
        "explanation": "仅基于候选关系和来源引用生成。",
    }
    payload.update(overrides)
    return CandidateReviewSuggestionOutput.model_validate(payload)


def test_candidate_policy_accepts_known_source_ref_ids() -> None:
    validate_candidate_review_suggestion_policy(
        suggestion_output(),
        allowed_source_ref_ids={101, 102},
    )


def test_candidate_policy_rejects_unknown_source_ref_ids() -> None:
    with raises(AIOutputPolicyViolation, match="unknown source_ref_id"):
        validate_candidate_review_suggestion_policy(
            suggestion_output(supporting_source_ref_ids=[999]),
            allowed_source_ref_ids={101, 102},
        )


def test_candidate_policy_rejects_empty_explanation_after_strip() -> None:
    output = suggestion_output(explanation="   ")

    with raises(AIOutputPolicyViolation, match="explanation is required"):
        validate_candidate_review_suggestion_policy(output, allowed_source_ref_ids={101})


def test_candidate_policy_accepts_known_retrieval_ids() -> None:
    validate_candidate_review_suggestion_policy(
        suggestion_output(
            retrieval_source_ref_ids=[3853784],
            retrieval_document_ids=["00000000-0000-0000-0000-000000000501"],
        ),
        allowed_source_ref_ids={101},
        allowed_retrieval_source_ref_ids={3853784},
        allowed_retrieval_document_ids={"00000000-0000-0000-0000-000000000501"},
    )


def test_candidate_policy_rejects_unknown_retrieval_source_ref_id() -> None:
    with raises(AIOutputPolicyViolation, match="unknown retrieval source_ref_id"):
        validate_candidate_review_suggestion_policy(
            suggestion_output(retrieval_source_ref_ids=[999999]),
            allowed_source_ref_ids={101},
            allowed_retrieval_source_ref_ids={3853784},
            allowed_retrieval_document_ids=set(),
        )


def test_candidate_policy_rejects_unknown_retrieval_document_id() -> None:
    with raises(AIOutputPolicyViolation, match="unknown retrieval document_id"):
        validate_candidate_review_suggestion_policy(
            suggestion_output(retrieval_document_ids=["missing-document"]),
            allowed_source_ref_ids={101},
            allowed_retrieval_source_ref_ids=set(),
            allowed_retrieval_document_ids={"00000000-0000-0000-0000-000000000501"},
        )
