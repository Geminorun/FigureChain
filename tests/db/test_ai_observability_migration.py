from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260619_0003_ai_observability_prompt_versioning.py")


def test_ai_observability_migration_extends_ai_runs() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "provider_request_id" in source
    assert "latency_ms" in source
    assert "prompt_tokens" in source
    assert "completion_tokens" in source
    assert "total_tokens" in source
    assert "estimated_cost" in source
    assert "cost_currency" in source
    assert "retry_count" in source
    assert "provider_metadata" in source


def test_ai_observability_migration_does_not_recreate_existing_job_events() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'op.create_table("ai_job_events"' not in source
    assert 'op.drop_table("ai_job_events"' not in source
