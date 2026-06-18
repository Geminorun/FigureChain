from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class PersonAliasDetail:
    alias_zh_hant: str | None
    alias_zh_hans: str | None
    alias_romanized: str | None
    alias_type_label_zh: str | None
    alias_type_label_en: str | None


@dataclass(frozen=True)
class PersonExternalIdDetail:
    source_name: str
    external_id: str


@dataclass(frozen=True)
class PersonEncounterSummaryCounts:
    active_count: int
    path_eligible_count: int
    high_certainty_count: int


@dataclass(frozen=True)
class PersonDetail:
    person_id: UUID
    primary_name_zh_hant: str | None
    primary_name_zh_hans: str | None
    primary_name_romanized: str | None
    birth_year: int | None
    death_year: int | None
    index_year: int | None
    floruit_start_year: int | None
    floruit_end_year: int | None
    dynasty_code: int | None
    dynasty_label_zh: str | None
    dynasty_label_en: str | None
    is_female: bool | None
    notes: str | None
    aliases: list[PersonAliasDetail]
    external_ids: list[PersonExternalIdDetail]
    encounter_summary: PersonEncounterSummaryCounts


@dataclass(frozen=True)
class PersonEncounterItem:
    encounter_id: UUID
    other_person_id: UUID
    other_person_name: str | None
    other_person_birth_year: int | None
    other_person_death_year: int | None
    encounter_kind: str
    certainty_level: str
    path_eligible: bool
    source_work_id: int | None
    source_title: str | None
    pages: str | None
    evidence_summary: str
    status: str
    reviewed_by: str
    reviewed_at: datetime
