from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260619_0001_create_chain_share_snapshots.py")


def test_share_snapshot_migration_uses_explicit_operations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in migration_source
    assert "Base.metadata.drop_all" not in migration_source
    assert 'op.create_table("chain_share_snapshots"' in migration_source
    assert 'op.create_table("chain_export_records"' in migration_source
    assert 'op.drop_table("chain_export_records"' in migration_source
    assert 'op.drop_table("chain_share_snapshots"' in migration_source


def test_share_snapshot_migration_declares_schema_and_indexes() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'schema="figure_data"' in migration_source or "schema=SCHEMA" in migration_source
    assert "uq_chain_share_snapshots_share_slug" in migration_source
    assert "ix_figure_data_chain_share_snapshots_chain_hash" in migration_source


def test_share_snapshot_migration_declares_export_constraints() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "fk_chain_export_records_share_snapshot_id_chain_share_snapshots" in migration_source
    assert "ck_chain_export_records_format" in migration_source
