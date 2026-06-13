from sqlalchemy import CheckConstraint, UniqueConstraint

from figure_data.db.base import Base
from figure_data.db.models import ai


def test_ai_models_use_figure_data_schema() -> None:
    assert ai
    assert Base.metadata.tables["figure_data.ai_prompt_versions"].schema == "figure_data"
    assert Base.metadata.tables["figure_data.ai_runs"].schema == "figure_data"


def test_ai_prompt_versions_have_unique_key_version() -> None:
    table = Base.metadata.tables["figure_data.ai_prompt_versions"]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert ("prompt_key", "prompt_version") in unique_columns
    assert "ck_ai_prompt_versions_status" in check_names


def test_ai_runs_link_prompt_version_and_declare_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_runs"]

    foreign_keys = {
        foreign_key.target_fullname for foreign_key in table.c.prompt_version_id.foreign_keys
    }
    index_names = {index.name for index in table.indexes}
    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "figure_data.ai_prompt_versions.id" in foreign_keys
    assert "ck_ai_runs_status" in check_names
    assert {
        "ix_figure_data_ai_runs_status",
        "ix_figure_data_ai_runs_purpose",
        "ix_figure_data_ai_runs_prompt_version_id",
        "ix_figure_data_ai_runs_input_hash",
    }.issubset(index_names)
