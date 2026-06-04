from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import Insert, insert

SOURCE_IDENTITY_COLUMNS = ("source_name", "source_table", "source_pk")


def build_upsert_statement(
    table: Table,
    rows: Sequence[Mapping[str, Any]],
    *,
    protected_columns: set[str] | None = None,
) -> Insert:
    protected = protected_columns or set()
    statement = insert(table).values(list(rows))
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
