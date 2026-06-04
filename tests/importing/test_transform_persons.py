from uuid import UUID

from figure_data.importing.context import ImportContext
from figure_data.importing.persons import transform_person_row


def test_transform_person_row_normalizes_names_and_dates() -> None:
    context = ImportContext(source_name="cbdb", source_snapshot="cbdb_20260530")
    row = {
        "c_personid": 25403,
        "c_name_chn": "諸葛亮",
        "c_name": "Zhuge Liang",
        "c_birthyear": 181,
        "c_deathyear": 234,
        "c_index_year": 220,
        "c_female": 0,
        "c_dy": 30,
        "c_notes": "sample",
    }

    record = transform_person_row(row, context)

    assert UUID(record["id"])
    assert record["primary_name_zh_hant"] == "諸葛亮"
    assert record["primary_name_zh_hans"] == "诸葛亮"
    assert record["birth_year"] == 181
    assert record["source_pk"] == "c_personid=25403"
