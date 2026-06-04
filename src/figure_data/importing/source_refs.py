from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.cbdb.normalize import normalize_int, normalize_text
from figure_data.cbdb.source_identity import build_rowid_source_pk, hash_source_row
from figure_data.cbdb.sqlite_reader import SQLiteReader
from figure_data.db.models.source import SourceRef
from figure_data.importing.context import ImportContext, ImportPhaseResult, imported_record_fields
from figure_data.importing.upsert import DEFAULT_UPSERT_CHUNK_SIZE, UpsertStats, execute_upsert_rows

_SOURCE_REF_KEYS = {
    "ASSOC_DATA": [
        "c_personid",
        "c_assoc_code",
        "c_assoc_id",
        "c_assoc_first_year",
        "c_sequence",
        "c_source",
    ],
    "KIN_DATA": ["c_personid", "c_kin_id", "c_kin_code", "c_source"],
    "POSTED_TO_OFFICE_DATA": ["c_personid", "c_office_id", "c_posting_id", "c_source"],
}


def import_source_refs(
    session: Session,
    reader: SQLiteReader,
    context: ImportContext,
    import_batch_id: UUID,
) -> ImportPhaseResult:
    imported_at = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    rows_read = 0
    upsert_stats = UpsertStats()
    for table_name, key_columns in _SOURCE_REF_KEYS.items():
        for row in reader.iter_rows(table_name):
            source_work_id = normalize_int(row.get("c_source"))
            if source_work_id is None:
                continue
            ref_source_pk = build_rowid_source_pk(row, key_columns)
            source_row_hash = hash_source_row(row)
            source_pk = build_source_ref_source_pk(table_name, row)
            rows.append(
                {
                    "source_work_id": source_work_id,
                    "ref_source_table": table_name,
                    "ref_source_pk": ref_source_pk,
                    "pages": normalize_text(row.get("c_pages")),
                    "notes": normalize_text(row.get("c_notes")),
                    **imported_record_fields(
                        context=context,
                        source_table=table_name,
                        source_pk=source_pk,
                        source_row_hash=source_row_hash,
                        raw_cbdb=dict(row),
                        import_batch_id=import_batch_id,
                        imported_at=imported_at,
                    ),
                }
            )
            rows_read += 1
            if len(rows) >= DEFAULT_UPSERT_CHUNK_SIZE:
                upsert_stats.add(execute_upsert_rows(session, SourceRef.__table__, rows))
                rows.clear()
    upsert_stats.add(execute_upsert_rows(session, SourceRef.__table__, rows))
    return ImportPhaseResult(rows_read=rows_read, upsert_stats=upsert_stats)


def build_source_ref_source_pk(table_name: str, row: dict[str, Any]) -> str:
    key_columns = _SOURCE_REF_KEYS[table_name]
    ref_source_pk = build_rowid_source_pk(row, key_columns)
    return f"ref_source_table={table_name}|ref_source_pk={ref_source_pk}"
