from sqlalchemy import CheckConstraint, UniqueConstraint

from figure_data.db.base import Base
from figure_data.db.enums import AIChainExplanationStatus, AIErrorCode
from figure_data.db.models import ai_chain


def test_ai_chain_explanation_enums_define_values() -> None:
    assert AIChainExplanationStatus.GENERATED.value == "generated"
    assert AIChainExplanationStatus.ARCHIVED.value == "archived"
    assert AIErrorCode.INVALID_CHAIN_CONTEXT.value == "invalid_chain_context"


def test_ai_chain_explanation_model_uses_figure_data_schema() -> None:
    assert ai_chain
    assert Base.metadata.tables["figure_data.ai_chain_explanations"].schema == "figure_data"


def test_ai_chain_explanation_model_links_ai_run() -> None:
    table = Base.metadata.tables["figure_data.ai_chain_explanations"]
    foreign_keys = {foreign_key.target_fullname for foreign_key in table.c.ai_run_id.foreign_keys}

    assert "figure_data.ai_runs.id" in foreign_keys


def test_ai_chain_explanation_model_declares_constraints() -> None:
    table = Base.metadata.tables["figure_data.ai_chain_explanations"]
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

    assert "ck_ai_chain_explanations_status" in check_names
    assert "ck_ai_chain_explanations_max_depth" in check_names
    assert ("chain_hash",) in unique_columns


def test_ai_chain_explanation_model_declares_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_chain_explanations"]
    index_names = {index.name for index in table.indexes}

    assert {
        "ix_figure_data_ai_chain_explanations_source_target",
        "ix_figure_data_ai_chain_explanations_ai_run_id",
        "ix_figure_data_ai_chain_explanations_status",
        "ix_figure_data_ai_chain_explanations_created_at",
    }.issubset(index_names)
