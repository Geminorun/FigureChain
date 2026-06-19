from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.ai.redaction import redact_sensitive_text
from figure_data.graph.types import GraphProjectionBatchRecord


def start_projection_batch(
    session: Session,
    *,
    mode: str,
    triggered_by: str,
    source_watermark: datetime | None,
) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.graph_projection_batches (
              id, mode, status, triggered_by, source_watermark,
              encounters_seen, relationships_written, relationships_deleted,
              persons_written, validation_status, validation_summary,
              error_code, error_message, started_at, finished_at
            ) values (
              gen_random_uuid(), :mode, :status, :triggered_by, :source_watermark,
              0, 0, 0, 0, :validation_status, cast(:validation_summary as jsonb),
              null, null, :started_at, null
            )
            returning id
            """
        ),
        {
            "mode": mode,
            "status": "running",
            "triggered_by": triggered_by,
            "source_watermark": source_watermark,
            "validation_status": "not_run",
            "validation_summary": "{}",
            "started_at": datetime.now(UTC),
        },
    ).scalar_one()
    return value if isinstance(value, UUID) else UUID(str(value))


def mark_projection_batch_succeeded(
    session: Session,
    *,
    batch_id: UUID,
    encounters_seen: int,
    persons_written: int,
    relationships_written: int,
    relationships_deleted: int,
    validation_status: str = "not_run",
    validation_summary: dict[str, object] | None = None,
) -> None:
    session.execute(
        text(
            """
            update figure_data.graph_projection_batches
            set status = :status,
                encounters_seen = :encounters_seen,
                persons_written = :persons_written,
                relationships_written = :relationships_written,
                relationships_deleted = :relationships_deleted,
                validation_status = :validation_status,
                validation_summary = cast(:validation_summary as jsonb),
                error_code = null,
                error_message = null,
                finished_at = :finished_at
            where id = :batch_id
            """
        ),
        {
            "batch_id": batch_id,
            "status": "succeeded",
            "encounters_seen": encounters_seen,
            "persons_written": persons_written,
            "relationships_written": relationships_written,
            "relationships_deleted": relationships_deleted,
            "validation_status": validation_status,
            "validation_summary": json.dumps(
                validation_summary or {},
                ensure_ascii=False,
                sort_keys=True,
            ),
            "finished_at": datetime.now(UTC),
        },
    )


def mark_projection_batch_failed(
    session: Session,
    *,
    batch_id: UUID,
    error_code: str,
    error_message: str,
) -> None:
    session.execute(
        text(
            """
            update figure_data.graph_projection_batches
            set status = :status,
                error_code = :error_code,
                error_message = :error_message,
                finished_at = :finished_at
            where id = :batch_id
            """
        ),
        {
            "batch_id": batch_id,
            "status": "failed",
            "error_code": error_code,
            "error_message": redact_sensitive_text(error_message),
            "finished_at": datetime.now(UTC),
        },
    )


def get_latest_projection_batch(
    session: Session,
    *,
    status: str | None = None,
) -> GraphProjectionBatchRecord | None:
    where = "" if status is None else "where status = :status"
    row = (
        session.execute(
            text(
                f"""
                select id, mode, status, triggered_by, source_watermark,
                       encounters_seen, relationships_written, relationships_deleted,
                       persons_written, validation_status, validation_summary,
                       error_code, error_message, started_at, finished_at
                from figure_data.graph_projection_batches
                {where}
                order by started_at desc, id desc
                limit 1
                """
            ),
            {"status": status} if status is not None else {},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return _record_from_row(cast(Mapping[str, Any], row))


def _record_from_row(row: Mapping[str, Any]) -> GraphProjectionBatchRecord:
    return GraphProjectionBatchRecord(
        id=str(row["id"]),
        mode=str(row["mode"]),
        status=str(row["status"]),
        triggered_by=str(row["triggered_by"]),
        source_watermark=row["source_watermark"],
        encounters_seen=int(row["encounters_seen"]),
        relationships_written=int(row["relationships_written"]),
        relationships_deleted=int(row["relationships_deleted"]),
        persons_written=int(row["persons_written"]),
        validation_status=str(row["validation_status"]),
        validation_summary=_json_object(row["validation_summary"]),
        error_code=row["error_code"],
        error_message=row["error_message"],
        started_at=cast(datetime, row["started_at"]),
        finished_at=cast(datetime | None, row["finished_at"]),
    )


def _json_object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        loaded = json.loads(value)
        return dict(loaded) if isinstance(loaded, dict) else {}
    return {}
