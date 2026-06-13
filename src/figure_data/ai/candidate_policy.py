from figure_data.ai.errors import AIOutputPolicyViolation
from figure_data.ai.schemas import CandidateReviewSuggestionOutput


def validate_candidate_review_suggestion_policy(
    output: CandidateReviewSuggestionOutput,
    *,
    allowed_source_ref_ids: set[int],
) -> None:
    unknown_source_ref_ids = [
        source_ref_id
        for source_ref_id in output.supporting_source_ref_ids
        if source_ref_id not in allowed_source_ref_ids
    ]
    if unknown_source_ref_ids:
        joined = ",".join(str(source_ref_id) for source_ref_id in unknown_source_ref_ids)
        raise AIOutputPolicyViolation(f"unknown source_ref_id in AI output: {joined}")
    if not output.explanation.strip():
        raise AIOutputPolicyViolation("explanation is required")
    if not output.evidence_summary_draft.strip():
        raise AIOutputPolicyViolation("evidence_summary_draft is required")
