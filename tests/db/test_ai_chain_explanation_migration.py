from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260613_0003_create_ai_chain_explanations.py")


def test_ai_chain_explanation_migration_depends_on_candidate_suggestions() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "20260613_0003"' in migration_source
    assert 'down_revision: str | None = "20260613_0002"' in migration_source


def test_ai_chain_explanation_migration_uses_explicit_operations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in migration_source
    assert "Base.metadata.drop_all" not in migration_source
    assert "DROP SCHEMA" not in migration_source
    assert 'op.create_table("ai_chain_explanations"' in migration_source
    assert 'op.drop_table("ai_chain_explanations"' in migration_source


def test_ai_chain_explanation_migration_declares_constraints() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "fk_ai_chain_explanations_ai_run_id_ai_runs" in migration_source
    assert "uq_ai_chain_explanations_chain_hash" in migration_source
    assert "ck_ai_chain_explanations_status" in migration_source
    assert "ck_ai_chain_explanations_max_depth" in migration_source
