from figure_data.validation.row_counts import (
    EXPECTED_CBDB_TABLES,
    EXPECTED_POSTGRES_TABLES,
    validate_expected_postgres_counts,
)


def test_expected_cbdb_tables_include_core_sources() -> None:
    assert EXPECTED_CBDB_TABLES["BIOG_MAIN"] == 658_670
    assert EXPECTED_CBDB_TABLES["ASSOC_DATA"] == 188_649
    assert EXPECTED_CBDB_TABLES["KIN_DATA"] == 557_265


def test_expected_postgres_tables_include_import_targets() -> None:
    assert EXPECTED_POSTGRES_TABLES["persons"] == 658_670
    assert EXPECTED_POSTGRES_TABLES["person_external_ids"] == 658_669
    assert EXPECTED_POSTGRES_TABLES["person_aliases"] == 207_219
    assert EXPECTED_POSTGRES_TABLES["relationship_candidates"] == 188_649
    assert EXPECTED_POSTGRES_TABLES["kinship_candidates"] == 557_265
    assert EXPECTED_POSTGRES_TABLES["office_postings"] == 588_501


def test_validate_expected_postgres_counts_reports_target_tables() -> None:
    assert callable(validate_expected_postgres_counts)
