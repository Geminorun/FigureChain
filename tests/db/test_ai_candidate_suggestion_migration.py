from pathlib import Path

MIGRATION_PATH = Path(
    "alembic/versions/20260613_0002_create_ai_candidate_review_suggestions.py"
)


def test_ai_candidate_suggestion_migration_exists_and_depends_on_ai_foundation() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "20260613_0002"' in migration_source
    assert 'down_revision: str | None = "20260613_0001"' in migration_source


def test_ai_candidate_suggestion_migration_uses_explicit_operations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in migration_source
    assert "Base.metadata.drop_all" not in migration_source
    assert "DROP SCHEMA" not in migration_source
    assert 'op.create_table("ai_candidate_review_suggestions"' in migration_source
    assert 'op.drop_table("ai_candidate_review_suggestions"' in migration_source


def test_ai_candidate_suggestion_migration_declares_constraints() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "fk_ai_candidate_review_suggestions_ai_run_id_ai_runs" in migration_source
    assert "uq_ai_candidate_review_suggestions_run_candidate" in migration_source
    assert "ck_ai_candidate_review_suggestions_kind" in migration_source
    assert "ck_ai_candidate_review_suggestions_action" in migration_source
    assert "ck_ai_candidate_review_suggestions_status" in migration_source
    assert "ck_ai_candidate_review_suggestions_priority_score" in migration_source
