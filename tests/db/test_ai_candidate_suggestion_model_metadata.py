from sqlalchemy import CheckConstraint, UniqueConstraint

from figure_data.db.base import Base
from figure_data.db.enums import (
    AICandidateReviewSuggestedAction,
    AICandidateSuggestionStatus,
)
from figure_data.db.models import ai_candidate


def test_ai_candidate_suggestion_enums_define_values() -> None:
    assert AICandidateReviewSuggestedAction.PROMOTE_CANDIDATE.value == "promote_candidate"
    assert AICandidateReviewSuggestedAction.NEEDS_HUMAN_REVIEW.value == (
        "needs_human_review"
    )
    assert AICandidateReviewSuggestedAction.REJECT_DUPLICATE.value == "reject_duplicate"
    assert AICandidateReviewSuggestedAction.INSUFFICIENT_EVIDENCE.value == (
        "insufficient_evidence"
    )
    assert AICandidateReviewSuggestedAction.NOT_PATH_CANDIDATE.value == (
        "not_path_candidate"
    )
    assert AICandidateSuggestionStatus.GENERATED.value == "generated"
    assert AICandidateSuggestionStatus.ARCHIVED.value == "archived"


def test_ai_candidate_suggestion_model_uses_figure_data_schema() -> None:
    assert ai_candidate
    assert (
        Base.metadata.tables["figure_data.ai_candidate_review_suggestions"].schema
        == "figure_data"
    )


def test_ai_candidate_suggestion_model_links_ai_run() -> None:
    table = Base.metadata.tables["figure_data.ai_candidate_review_suggestions"]

    foreign_keys = {
        foreign_key.target_fullname for foreign_key in table.c.ai_run_id.foreign_keys
    }

    assert "figure_data.ai_runs.id" in foreign_keys


def test_ai_candidate_suggestion_model_declares_constraints() -> None:
    table = Base.metadata.tables["figure_data.ai_candidate_review_suggestions"]

    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert "ck_ai_candidate_review_suggestions_kind" in check_names
    assert "ck_ai_candidate_review_suggestions_action" in check_names
    assert "ck_ai_candidate_review_suggestions_status" in check_names
    assert "ck_ai_candidate_review_suggestions_priority_score" in check_names
    assert ("ai_run_id", "candidate_kind", "candidate_id") in unique_columns


def test_ai_candidate_suggestion_model_declares_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_candidate_review_suggestions"]
    index_names = {index.name for index in table.indexes}

    assert {
        "ix_figure_data_ai_candidate_review_suggestions_candidate",
        "ix_figure_data_ai_candidate_review_suggestions_status",
        "ix_figure_data_ai_candidate_review_suggestions_action",
        "ix_figure_data_ai_candidate_review_suggestions_created_at",
    }.issubset(index_names)
