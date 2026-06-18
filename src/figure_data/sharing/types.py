from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class NewChainShareSnapshot:
    source_person_id: UUID
    target_person_id: UUID
    chain_hash: str
    encounter_ids: list[str]
    path_payload: dict[str, object]
    filters_applied: dict[str, object]
    include_ai_explanation: bool
    include_rag_context: bool
    schema_version: str
    created_by: str | None


@dataclass(frozen=True)
class ChainShareSnapshotRecord(NewChainShareSnapshot):
    id: UUID
    share_slug: str
    created_at: datetime


@dataclass(frozen=True)
class MarkdownExportRecord:
    id: UUID
    share_snapshot_id: UUID
    format: str
    filename: str
    source_ids: dict[str, list[str]]
    created_at: datetime
