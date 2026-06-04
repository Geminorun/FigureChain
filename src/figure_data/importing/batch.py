from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from figure_data.config import Settings
from figure_data.db.models.import_batch import ImportBatch


def start_import_batch(
    session: Session,
    settings: Settings,
    metadata: dict[str, Any],
) -> ImportBatch:
    sqlite_filename = str(metadata.get("sqlite_filename") or Path(settings.cbdb_sqlite_path).name)
    sqlite_sha256 = str(metadata.get("sha256") or "")
    batch = ImportBatch(
        source_name=settings.source_name,
        source_snapshot=settings.source_snapshot,
        sqlite_filename=sqlite_filename,
        sqlite_sha256=sqlite_sha256,
        started_at=datetime.now(UTC),
        status="running",
        rows_read=0,
        rows_inserted=0,
        rows_updated=0,
        rows_skipped=0,
        error_count=0,
    )
    session.add(batch)
    session.flush()
    return batch


def finish_import_batch(session: Session, batch: ImportBatch, *, rows_read: int) -> None:
    batch.finished_at = datetime.now(UTC)
    batch.status = "succeeded"
    batch.rows_read = rows_read
    session.add(batch)


def fail_import_batch(session: Session, batch: ImportBatch, error: Exception) -> None:
    batch.finished_at = datetime.now(UTC)
    batch.status = "failed"
    batch.error_count = 1
    batch.error_summary = str(error)
    session.add(batch)
