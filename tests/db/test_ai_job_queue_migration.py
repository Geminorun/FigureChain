from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260619_0002_extend_ai_jobs_for_rq.py")


def test_queue_migration_extends_ai_generation_jobs() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'op.add_column("ai_generation_jobs"' in source
    assert "queue_backend" in source
    assert "queue_job_id" in source
    assert "attempt_count" in source
    assert "heartbeat_at" in source


def test_queue_migration_creates_ai_job_events() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'op.create_table("ai_job_events"' in source
    assert 'op.drop_table("ai_job_events"' in source
    assert "ix_figure_data_ai_job_events_job_created_at" in source
