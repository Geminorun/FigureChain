from uuid import UUID

from pytest import raises

from figure_data.encounters.types import (
    EncounterOperationError,
    EncounterPromotionOptions,
    EncounterRetractionOptions,
    require_non_blank,
)
from figure_data.review.types import CandidateKind


def test_promotion_options_normalize_required_text() -> None:
    options = EncounterPromotionOptions(
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=123,
        reviewed_by=" lyl ",
        evidence_summary=" 有直接互动证据 ",
        review_note=" 史料页码明确 ",
    )

    assert options.reviewed_by == "lyl"
    assert options.evidence_summary == "有直接互动证据"
    assert options.review_note == "史料页码明确"


def test_promotion_options_require_evidence_summary() -> None:
    with raises(EncounterOperationError, match="evidence_summary is required"):
        EncounterPromotionOptions(
            candidate_kind=CandidateKind.RELATIONSHIP,
            candidate_id=123,
            reviewed_by="lyl",
            evidence_summary=" ",
        )


def test_retraction_options_require_note() -> None:
    with raises(EncounterOperationError, match="note is required"):
        EncounterRetractionOptions(
            encounter_id=UUID("00000000-0000-0000-0000-000000000001"),
            reviewed_by="lyl",
            note=" ",
        )


def test_require_non_blank_returns_trimmed_text() -> None:
    assert require_non_blank(" review ", field_name="reviewed_by") == "review"
