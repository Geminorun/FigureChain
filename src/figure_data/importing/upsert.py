from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import FromClause

SOURCE_IDENTITY_COLUMNS = ("source_name", "source_table", "source_pk")
DEFAULT_UPSERT_CHUNK_SIZE = 500


@dataclass
class UpsertStats:
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_skipped: int = 0

    def add(self, other: UpsertStats) -> None:
        self.rows_inserted += other.rows_inserted
        self.rows_updated += other.rows_updated
        self.rows_skipped += other.rows_skipped


def build_upsert_statement(
    table: FromClause,
    rows: Sequence[Mapping[str, Any]],
    *,
    protected_columns: set[str] | None = None,
) -> Insert:
    protected = protected_columns or set()
    statement = insert(cast(Any, table)).values(list(rows))
    update_columns = {
        column.name: getattr(statement.excluded, column.name)
        for column in table.columns
        if column.name not in SOURCE_IDENTITY_COLUMNS
        and column.name not in protected
        and not column.primary_key
    }
    returning_statement: Any = statement.on_conflict_do_update(
        index_elements=list(SOURCE_IDENTITY_COLUMNS),
        set_=update_columns,
    ).returning(
        literal_column("xmax = 0").label("inserted"),
    )
    return cast(Insert, returning_statement)


def execute_upsert_rows(
    session: Session,
    table: FromClause,
    rows: Sequence[Mapping[str, Any]],
    *,
    protected_columns: set[str] | None = None,
    chunk_size: int = DEFAULT_UPSERT_CHUNK_SIZE,
) -> UpsertStats:
    stats = UpsertStats()
    for start in range(0, len(rows), chunk_size):
        chunk = _deduplicate_source_identity(rows[start : start + chunk_size])
        if not chunk:
            stats.rows_skipped += len(rows[start : start + chunk_size])
            continue
        result = session.execute(
            build_upsert_statement(
                table,
                chunk,
                protected_columns=protected_columns,
            )
        )
        inserted_flags = [bool(row.inserted) for row in result]
        stats.rows_inserted += sum(1 for inserted in inserted_flags if inserted)
        stats.rows_updated += sum(1 for inserted in inserted_flags if not inserted)
        stats.rows_skipped += len(rows[start : start + chunk_size]) - len(chunk)
    return stats


def _deduplicate_source_identity(
    rows: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    deduplicated: dict[tuple[Any | None, Any | None, Any | None], Mapping[str, Any]] = {}
    for row in rows:
        key = (
            row.get(SOURCE_IDENTITY_COLUMNS[0]),
            row.get(SOURCE_IDENTITY_COLUMNS[1]),
            row.get(SOURCE_IDENTITY_COLUMNS[2]),
        )
        deduplicated[key] = row
    return list(deduplicated.values())
