from figure_data.validation.row_counts import EXPECTED_CBDB_TABLES


def test_expected_cbdb_tables_include_core_sources() -> None:
    assert EXPECTED_CBDB_TABLES["BIOG_MAIN"] == 658_670
    assert EXPECTED_CBDB_TABLES["ASSOC_DATA"] == 188_649
    assert EXPECTED_CBDB_TABLES["KIN_DATA"] == 557_265
