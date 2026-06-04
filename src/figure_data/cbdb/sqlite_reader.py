from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType
from typing import Any


class SQLiteReader:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> SQLiteReader:
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def iter_rows(self, table_name: str) -> Iterator[dict[str, Any]]:
        if self._conn is None:
            raise RuntimeError("SQLiteReader must be used as a context manager")
        cursor = self._conn.execute(f"select rowid as _rowid, * from {table_name} order by rowid")
        for row in cursor:
            yield dict(row)
