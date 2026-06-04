from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import FromClause

SOURCE_IDENTITY_COLUMNS = ("source_name", "source_table", "source_pk")
DEFAULT_UPSERT_CHUNK_SIZE = 500


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
    return statement.on_conflict_do_update(
        index_elements=list(SOURCE_IDENTITY_COLUMNS),
        set_=update_columns,
    )


def execute_upsert_rows(
    session: Session,
    table: FromClause,
    rows: Sequence[Mapping[str, Any]],
    *,
    protected_columns: set[str] | None = None,
    chunk_size: int = DEFAULT_UPSERT_CHUNK_SIZE,
) -> int:
    total = 0
    for start in range(0, len(rows), chunk_size):
        chunk = _deduplicate_source_identity(rows[start : start + chunk_size])
        if not chunk:
            continue
        session.execute(
            build_upsert_statement(
                table,
                chunk,
                protected_columns=protected_columns,
            )
        )
        total += len(chunk)
    return total


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
