import hashlib
import json
from pathlib import Path

from figure_data.cbdb.snapshot import load_snapshot_metadata, verify_sqlite_sha256


def test_load_snapshot_metadata_reads_json(tmp_path: Path) -> None:
    metadata_path = tmp_path / "cbdb.json"
    metadata_path.write_text(json.dumps({"sqlite_filename": "cbdb.sqlite3"}), encoding="utf-8")

    metadata = load_snapshot_metadata(metadata_path)

    assert metadata["sqlite_filename"] == "cbdb.sqlite3"


def test_verify_sqlite_sha256_accepts_matching_hash(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "cbdb.sqlite3"
    sqlite_path.write_bytes(b"abc")
    expected = hashlib.sha256(b"abc").hexdigest()

    assert verify_sqlite_sha256(sqlite_path, expected) == expected
