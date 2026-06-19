from __future__ import annotations

from pathlib import Path


MIGRATION = Path("alembic/versions/20260619_0004_create_graph_projection_batches.py")


def test_graph_projection_batch_migration_creates_expected_table() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "create_table" in source
    assert "graph_projection_batches" in source
    assert "create_index" in source
    assert "drop_table" in source
