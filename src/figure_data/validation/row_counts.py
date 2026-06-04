from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.cbdb.sqlite_reader import SQLiteReader
from figure_data.validation.report import ValidationCheck

EXPECTED_CBDB_TABLES = {
    "BIOG_MAIN": 658_670,
    "ALTNAME_DATA": 207_219,
    "ASSOC_DATA": 188_649,
    "KIN_DATA": 557_265,
    "TEXT_CODES": 61_146,
    "POSTED_TO_OFFICE_DATA": 588_501,
}


def count_sqlite_rows(reader: SQLiteReader, table_name: str) -> int:
    return sum(1 for _ in reader.iter_rows(table_name))


def count_postgres_rows(session: Session, table_name: str) -> int:
    return int(session.execute(text(f"select count(*) from figure_data.{table_name}")).scalar_one())


def validate_expected_sqlite_counts(reader: SQLiteReader) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    for table_name, expected in EXPECTED_CBDB_TABLES.items():
        actual = count_sqlite_rows(reader, table_name)
        checks.append(
            ValidationCheck(
                name=f"sqlite:{table_name}",
                passed=actual == expected,
                detail=f"expected={expected}, actual={actual}",
            )
        )
    return checks
