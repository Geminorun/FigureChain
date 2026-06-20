from __future__ import annotations

from pathlib import Path

MIGRATION = Path("alembic/versions/20260620_0001_create_admin_operations.py")


def test_admin_operation_migration_creates_expected_table() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "create_table" in source
    assert "admin_operations" in source
    assert "ck_admin_operations_status" in source
    assert "ix_figure_data_admin_operations_status_created_at" in source
    assert "ix_figure_data_admin_operations_type_created_at" in source
    assert "ix_figure_data_admin_operations_related_resource" in source
    assert "drop_table" in source
