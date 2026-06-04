from figure_data.importing.orchestrator import CBDB_IMPORT_TABLE_ORDER


def test_import_order_loads_people_before_relationships() -> None:
    assert CBDB_IMPORT_TABLE_ORDER.index("BIOG_MAIN") < CBDB_IMPORT_TABLE_ORDER.index("ASSOC_DATA")
    assert CBDB_IMPORT_TABLE_ORDER.index("BIOG_MAIN") < CBDB_IMPORT_TABLE_ORDER.index("KIN_DATA")
