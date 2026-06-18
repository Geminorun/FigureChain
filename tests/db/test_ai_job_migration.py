from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260618_0001_create_ai_generation_jobs.py")


def test_ai_job_migration_exists_and_depends_on_retrieval_tables() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "20260618_0001"' in migration_source
    assert 'down_revision: str | None = "20260613_0004"' in migration_source


def test_ai_job_migration_uses_explicit_operations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in migration_source
    assert "Base.metadata.drop_all" not in migration_source
    assert "DROP SCHEMA" not in migration_source
    assert 'op.create_table("ai_generation_jobs"' in migration_source
    assert 'op.drop_table("ai_generation_jobs"' in migration_source


def test_ai_job_migration_declares_constraints_and_indexes() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "ck_ai_generation_jobs_job_type" in migration_source
    assert "ck_ai_generation_jobs_target_type" in migration_source
    assert "ck_ai_generation_jobs_target_kind" in migration_source
    assert "ck_ai_generation_jobs_status" in migration_source
    assert "ix_figure_data_ai_generation_jobs_status_created_at" in migration_source
    assert "ix_figure_data_ai_generation_jobs_target" in migration_source
    assert "ix_figure_data_ai_generation_jobs_job_type_created_at" in migration_source
