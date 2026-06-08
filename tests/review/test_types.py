from pytest import raises

from figure_data.review.types import (
    CandidateKind,
    CandidateReviewError,
    CandidateReviewStatus,
    candidate_table_name,
    normalize_candidate_kind,
    require_review_text,
)


def test_candidate_kind_normalization_accepts_supported_values() -> None:
    assert normalize_candidate_kind("relationship") is CandidateKind.RELATIONSHIP
    assert normalize_candidate_kind("kinship") is CandidateKind.KINSHIP


def test_candidate_kind_normalization_rejects_unknown_values() -> None:
    with raises(CandidateReviewError, match="unsupported candidate kind"):
        normalize_candidate_kind("office")


def test_candidate_table_name_is_whitelisted() -> None:
    assert candidate_table_name(CandidateKind.RELATIONSHIP) == "relationship_candidates"
    assert candidate_table_name(CandidateKind.KINSHIP) == "kinship_candidates"


def test_review_text_must_not_be_blank() -> None:
    with raises(CandidateReviewError, match="reviewed_by is required"):
        require_review_text("  ", field_name="reviewed_by")


def test_review_status_values_match_existing_candidate_columns() -> None:
    assert CandidateReviewStatus.UNREVIEWED.value == "unreviewed"
    assert CandidateReviewStatus.NEEDS_REVIEW.value == "needs_review"
    assert CandidateReviewStatus.PROMOTED_TO_ENCOUNTER.value == "promoted_to_encounter"
    assert CandidateReviewStatus.REJECTED.value == "rejected"
