from __future__ import annotations

import json
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.sharing.types import (
    ChainShareSnapshotRecord,
    MarkdownExportRecord,
    NewChainShareSnapshot,
)


class ShareSnapshotNotFoundError(ValueError):
    """Raised when a chain share snapshot cannot be found."""


def create_share_snapshot(
    session: Session,
    snapshot: NewChainShareSnapshot,
) -> ChainShareSnapshotRecord:
    created_at = datetime.now(UTC)
    share_slug = _generate_share_slug(datetime.now().astimezone())
    row = (
        session.execute(
            text(
                """
                insert into figure_data.chain_share_snapshots (
                  id, share_slug, source_person_id, target_person_id, chain_hash,
                  encounter_ids, path_payload, filters_applied,
                  include_ai_explanation, include_rag_context, schema_version,
                  created_by, created_at
                ) values (
                  gen_random_uuid(), :share_slug, :source_person_id,
                  :target_person_id, :chain_hash, cast(:encounter_ids as jsonb),
                  cast(:path_payload as jsonb), cast(:filters_applied as jsonb),
                  :include_ai_explanation, :include_rag_context, :schema_version,
                  :created_by, :created_at
                )
                returning id, share_slug, created_at
                """
            ),
            {
                "share_slug": share_slug,
                "source_person_id": snapshot.source_person_id,
                "target_person_id": snapshot.target_person_id,
                "chain_hash": snapshot.chain_hash,
                "encounter_ids": _json(snapshot.encounter_ids),
                "path_payload": _json(snapshot.path_payload),
                "filters_applied": _json(snapshot.filters_applied),
                "include_ai_explanation": snapshot.include_ai_explanation,
                "include_rag_context": snapshot.include_rag_context,
                "schema_version": snapshot.schema_version,
                "created_by": snapshot.created_by,
                "created_at": created_at,
            },
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise RuntimeError("failed to create chain share snapshot")
    row_mapping = cast(Mapping[str, Any], row)
    return ChainShareSnapshotRecord(
        id=_uuid(row_mapping["id"]),
        share_slug=str(row_mapping["share_slug"]),
        source_person_id=snapshot.source_person_id,
        target_person_id=snapshot.target_person_id,
        chain_hash=snapshot.chain_hash,
        encounter_ids=snapshot.encounter_ids,
        path_payload=snapshot.path_payload,
        filters_applied=snapshot.filters_applied,
        include_ai_explanation=snapshot.include_ai_explanation,
        include_rag_context=snapshot.include_rag_context,
        schema_version=snapshot.schema_version,
        created_by=snapshot.created_by,
        created_at=_datetime(row_mapping["created_at"]),
    )


def get_share_snapshot_by_slug(session: Session, share_slug: str) -> ChainShareSnapshotRecord:
    row = (
        session.execute(
            text(
                """
                select
                  id, share_slug, source_person_id, target_person_id, chain_hash,
                  encounter_ids, path_payload, filters_applied,
                  include_ai_explanation, include_rag_context, schema_version,
                  created_by, created_at
                from figure_data.chain_share_snapshots
                where share_slug = :share_slug
                """
            ),
            {"share_slug": share_slug},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ShareSnapshotNotFoundError(f"chain share snapshot not found: {share_slug}")
    return _snapshot_from_row(cast(Mapping[str, Any], row))


def record_markdown_export(
    session: Session,
    share_snapshot_id: UUID,
    *,
    filename: str,
    source_ids: dict[str, list[str]],
) -> MarkdownExportRecord:
    row = (
        session.execute(
            text(
                """
                insert into figure_data.chain_export_records (
                  id, share_snapshot_id, format, filename, source_ids, created_at
                ) values (
                  gen_random_uuid(), :share_snapshot_id, :format, :filename,
                  cast(:source_ids as jsonb), :created_at
                )
                returning id, created_at
                """
            ),
            {
                "share_snapshot_id": share_snapshot_id,
                "format": "markdown",
                "filename": filename,
                "source_ids": _json(source_ids),
                "created_at": datetime.now(UTC),
            },
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise RuntimeError("failed to record markdown export")
    row_mapping = cast(Mapping[str, Any], row)
    return MarkdownExportRecord(
        id=_uuid(row_mapping["id"]),
        share_snapshot_id=share_snapshot_id,
        format="markdown",
        filename=filename,
        source_ids=source_ids,
        created_at=_datetime(row_mapping["created_at"]),
    )


def _snapshot_from_row(row: Mapping[str, Any]) -> ChainShareSnapshotRecord:
    return ChainShareSnapshotRecord(
        id=_uuid(row["id"]),
        share_slug=str(row["share_slug"]),
        source_person_id=_uuid(row["source_person_id"]),
        target_person_id=_uuid(row["target_person_id"]),
        chain_hash=str(row["chain_hash"]),
        encounter_ids=[str(item) for item in _loaded_list(row["encounter_ids"])],
        path_payload=_loaded_dict(row["path_payload"]),
        filters_applied=_loaded_dict(row["filters_applied"]),
        include_ai_explanation=bool(row["include_ai_explanation"]),
        include_rag_context=bool(row["include_rag_context"]),
        schema_version=str(row["schema_version"]),
        created_by=None if row["created_by"] is None else str(row["created_by"]),
        created_at=_datetime(row["created_at"]),
    )


def _generate_share_slug(created_at: datetime) -> str:
    return f"{created_at:%Y%m%d}-{secrets.token_urlsafe(8)}"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _loaded_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    return []


def _loaded_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return cast(dict[str, object], value)
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return {}
