from uuid import UUID

from figure_data.importing.aliases import transform_alias_row
from figure_data.importing.context import ImportContext
from figure_data.importing.kinship import transform_kinship_row
from figure_data.importing.offices import transform_office_posting_row
from figure_data.importing.orchestrator import _merge_kinship_source_row
from figure_data.importing.relationships import transform_relationship_row
from figure_data.importing.source_refs import build_source_ref_source_pk


def test_real_assoc_source_pk_uses_rowid_not_row_hash() -> None:
    context = ImportContext(source_name="cbdb", source_snapshot="cbdb_20260530")
    row = {
        "_rowid": 99,
        "c_personid": 25403,
        "c_assoc_id": 21204,
        "c_assoc_code": 95,
        "c_assoc_first_year": 231,
        "c_sequence": None,
    }

    record = transform_relationship_row(row, context)

    assert record["source_pk"] == "_rowid=99"
    assert "source_row_hash=" not in record["source_pk"]


def test_real_alias_source_pk_uses_rowid_not_row_hash() -> None:
    context = ImportContext(source_name="cbdb", source_snapshot="cbdb_20260530")
    row = {
        "_rowid": 12,
        "c_personid": 25403,
        "c_alt_name_chn": "孔明",
        "c_alt_name_type_code": 4,
        "c_sequence": None,
    }

    record = transform_alias_row(row, context, UUID("ff4246de-f40d-555b-aa70-c32a865e469f"))

    assert record["source_pk"] == "_rowid=12"
    assert "source_row_hash=" not in record["source_pk"]


def test_real_kinship_source_pk_uses_rowid_not_row_hash() -> None:
    context = ImportContext(source_name="cbdb", source_snapshot="cbdb_20260530")
    row = {
        "_rowid": 21,
        "c_personid": 25403,
        "c_kin_id": 21204,
        "c_kin_code": 75,
        "c_source": 1,
    }

    record = transform_kinship_row(row, context)

    assert record["source_pk"] == "_rowid=21"
    assert "source_row_hash=" not in record["source_pk"]


def test_kinship_code_merge_preserves_kin_data_rowid() -> None:
    source_row = _merge_kinship_source_row(
        {"_rowid": 21, "c_personid": 25403, "c_kin_code": 75},
        {"_rowid": 2, "c_kinrel_chn": "父"},
    )

    assert source_row["_rowid"] == 21
    assert source_row["c_kinrel_chn"] == "父"


def test_real_office_posting_source_pk_uses_rowid_not_row_hash() -> None:
    context = ImportContext(source_name="cbdb", source_snapshot="cbdb_20260530")
    row = {
        "_rowid": 31,
        "c_personid": 25403,
        "c_office_id": 1,
        "c_posting_id": 2,
        "c_firstyear": 231,
    }

    record = transform_office_posting_row(row, context)

    assert record["source_pk"] == "_rowid=31"
    assert "source_row_hash=" not in record["source_pk"]


def test_source_ref_source_pk_uses_source_table_and_rowid_not_row_hash() -> None:
    row = {
        "_rowid": 41,
        "c_personid": 25403,
        "c_assoc_id": 21204,
        "c_assoc_code": 95,
        "c_source": 1,
    }

    source_pk = build_source_ref_source_pk("ASSOC_DATA", row)

    assert source_pk == "ref_source_table=ASSOC_DATA|ref_source_pk=_rowid=41"
    assert "source_row_hash=" not in source_pk
