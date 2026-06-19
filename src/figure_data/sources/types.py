from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class SourceWorkDetail:
    source_work_id: int
    text_code: int | None
    title_zh: str | None
    title_en: str | None
    source_name: str
    source_table: str
    source_pk: str
    ref_count: int
    encounter_count: int


@dataclass(frozen=True)
class LinkedEncounterEvidence:
    evidence_id: int
    encounter_id: UUID
    evidence_kind: str
    evidence_summary: str
    pages: str | None
    created_at: datetime


@dataclass(frozen=True)
class SourceRefDetail:
    source_ref_id: int
    source_work: SourceWorkDetail | None
    ref_source_table: str
    ref_source_pk: str
    pages: str | None
    notes: str | None
    source_name: str
    source_table: str
    source_pk: str
    linked_encounter_evidence: list[LinkedEncounterEvidence]
