from sqlalchemy import CheckConstraint, UniqueConstraint

from figure_data.db.base import Base
from figure_data.db.enums import CertaintyLevel, EncounterKind, EncounterStatus
from figure_data.db.models import encounter


def test_encounter_enums_define_foundation_values() -> None:
    assert EncounterKind.DIRECT_INTERACTION == "direct_interaction"
    assert EncounterKind.CO_PRESENCE == "co_presence"
    assert EncounterKind.FAMILY_CONTACT == "family_contact"
    assert EncounterKind.MANUAL_CONTACT == "manual_contact"
    assert CertaintyLevel.HIGH == "high"
    assert CertaintyLevel.MEDIUM == "medium"
    assert CertaintyLevel.LOW == "low"
    assert EncounterStatus.ACTIVE == "active"
    assert EncounterStatus.RETRACTED == "retracted"


def test_encounter_models_use_figure_data_schema() -> None:
    assert encounter
    assert Base.metadata.tables["figure_data.encounters"].schema == "figure_data"
    assert Base.metadata.tables["figure_data.encounter_evidence"].schema == "figure_data"


def test_encounters_have_distinct_people_check_and_unique_identity() -> None:
    table = Base.metadata.tables["figure_data.encounters"]

    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert "ck_encounters_distinct_people" in check_names
    assert (
        "person_a_id",
        "person_b_id",
        "encounter_kind",
        "time_start_year",
        "time_end_year",
        "source_work_id",
        "pages",
    ) in unique_columns


def test_encounter_evidence_links_encounter_and_candidate_once() -> None:
    table = Base.metadata.tables["figure_data.encounter_evidence"]

    foreign_keys = {
        foreign_key.target_fullname for foreign_key in table.c.encounter_id.foreign_keys
    }
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert "figure_data.encounters.id" in foreign_keys
    assert ("encounter_id", "candidate_table", "candidate_id") in unique_columns
