from pathlib import Path

from figure_data.cbdb.sqlite_reader import SQLiteReader
from tests.fixtures.cbdb_minimal import create_minimal_cbdb_sqlite


def test_sqlite_reader_iterates_rows(tmp_path: Path) -> None:
    sqlite_path = create_minimal_cbdb_sqlite(tmp_path / "cbdb.sqlite3")

    with SQLiteReader(sqlite_path) as reader:
        rows = list(reader.iter_rows("BIOG_MAIN"))

    row_by_id = {row["c_personid"]: row for row in rows}
    assert isinstance(row_by_id[25403]["_rowid"], int)
    assert row_by_id[25403]["c_name_chn"] == "諸葛亮"
