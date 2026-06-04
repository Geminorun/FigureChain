from pathlib import Path

from sqlalchemy import UniqueConstraint
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.db.base import Base
from figure_data.db.models import identity, import_batch, office, person, relationship, source

MIGRATION_PATH = Path("alembic/versions/20260604_0001_create_figure_data_schema.py")


def test_models_use_figure_data_schema() -> None:
    modules = [import_batch, identity, office, person, relationship, source]
    assert modules

    for table in Base.metadata.tables.values():
        assert table.schema == "figure_data"


def test_relationship_candidates_have_stable_source_identity_constraint() -> None:
    table = Base.metadata.tables["figure_data.relationship_candidates"]
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("source_name", "source_table", "source_pk") in constraint_columns


def test_imported_rows_reference_import_batches() -> None:
    for table_name, table in Base.metadata.tables.items():
        if table_name == "figure_data.import_batches":
            continue
        if "import_batch_id" not in table.columns:
            continue

        foreign_keys = {
            foreign_key.target_fullname for foreign_key in table.c.import_batch_id.foreign_keys
        }

        assert "figure_data.import_batches.id" in foreign_keys


def test_identity_tables_are_manual_workflow_tables() -> None:
    manual_columns = {"created_at", "updated_at", "review_status"}
    imported_columns = {"source_table", "source_pk", "raw_cbdb", "import_batch_id"}

    for table_name in ("figure_data.person_merge_candidates", "figure_data.person_identity_links"):
        table = Base.metadata.tables[table_name]
        column_names = set(table.columns.keys())

        assert manual_columns <= column_names
        assert imported_columns.isdisjoint(column_names)


def test_person_external_ids_keep_source_identity() -> None:
    table = Base.metadata.tables["figure_data.person_external_ids"]

    assert {
        "source_name",
        "source_snapshot",
        "source_table",
        "source_pk",
        "source_row_hash",
        "raw_cbdb",
        "import_batch_id",
        "imported_at",
        "updated_at",
    } <= set(table.columns.keys())


def test_initial_migration_uses_explicit_operations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in migration_source
    assert "Base.metadata.drop_all" not in migration_source
    assert "DROP SCHEMA IF EXISTS figure_data CASCADE" not in migration_source
    assert "op.create_table(" in migration_source
    assert "op.drop_table(" in migration_source


def test_cli_entrypoint_loads_help() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
