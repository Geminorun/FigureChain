from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260608_0001_create_encounter_review_tables.py")


def test_encounter_migration_exists_and_depends_on_import_schema() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "20260608_0001"' in migration_source
    assert 'down_revision: str | None = "20260604_0001"' in migration_source


def test_encounter_migration_uses_explicit_operations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in migration_source
    assert "Base.metadata.drop_all" not in migration_source
    assert "DROP SCHEMA" not in migration_source
    assert 'op.create_table("encounters"' in migration_source
    assert 'op.create_table("encounter_evidence"' in migration_source
    assert 'op.drop_table("encounter_evidence"' in migration_source
    assert 'op.drop_table("encounters"' in migration_source


def test_encounter_migration_declares_core_constraints() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "ck_encounters_distinct_people" in migration_source
    assert "uq_encounters_pair_kind_time_source" in migration_source
    assert "uq_encounter_evidence_candidate" in migration_source
    assert "fk_encounters_person_a_id_persons" in migration_source
    assert "fk_encounters_person_b_id_persons" in migration_source
    assert "fk_encounter_evidence_encounter_id_encounters" in migration_source
