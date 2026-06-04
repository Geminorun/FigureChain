from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from figure_data.importing.upsert import UpsertStats


@dataclass(frozen=True)
class ImportContext:
    source_name: str
    source_snapshot: str


@dataclass(frozen=True)
class ImportPhaseResult:
    rows_read: int
    upsert_stats: UpsertStats


def imported_record_fields(
    *,
    context: ImportContext,
    source_table: str,
    source_pk: str,
    source_row_hash: str,
    raw_cbdb: dict[str, Any],
    import_batch_id: UUID,
    imported_at: datetime,
) -> dict[str, Any]:
    return {
        "source_name": context.source_name,
        "source_snapshot": context.source_snapshot,
        "source_table": source_table,
        "source_pk": source_pk,
        "source_row_hash": source_row_hash,
        "raw_cbdb": raw_cbdb,
        "import_batch_id": import_batch_id,
        "imported_at": imported_at,
        "updated_at": imported_at,
    }
