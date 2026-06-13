from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260613_0001_create_ai_foundation_tables.py")


def test_ai_migration_exists_and_depends_on_encounter_review_tables() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "20260613_0001"' in migration_source
    assert 'down_revision: str | None = "20260608_0001"' in migration_source


def test_ai_migration_uses_explicit_operations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in migration_source
    assert "Base.metadata.drop_all" not in migration_source
    assert "DROP SCHEMA" not in migration_source
    assert 'op.create_table("ai_prompt_versions"' in migration_source
    assert 'op.create_table("ai_runs"' in migration_source
    assert 'op.drop_table("ai_runs"' in migration_source
    assert 'op.drop_table("ai_prompt_versions"' in migration_source


def test_ai_migration_declares_core_constraints() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "uq_ai_prompt_versions_key_version" in migration_source
    assert "ck_ai_prompt_versions_status" in migration_source
    assert "ck_ai_runs_status" in migration_source
    assert "fk_ai_runs_prompt_version_id_ai_prompt_versions" in migration_source
    assert "ix_figure_data_ai_runs_status" in migration_source
