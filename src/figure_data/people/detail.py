from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.people.types import (
    PersonAliasDetail,
    PersonDetail,
    PersonEncounterItem,
    PersonEncounterSummaryCounts,
    PersonExternalIdDetail,
)


class PersonDetailNotFoundError(ValueError):
    """Raised when a person detail record cannot be found."""


@dataclass(frozen=True)
class PersonEncounterFilters:
    status: str | None = "active"
    path_eligible: bool | None = None
    certainty_level: str | None = None
    encounter_kind: str | None = None
    limit: int = 50
    offset: int = 0


PERSON_DETAIL_SQL = """
select
  p.id as person_id,
  p.primary_name_zh_hant,
  p.primary_name_zh_hans,
  p.primary_name_romanized,
  p.birth_year,
  p.death_year,
  p.index_year,
  p.floruit_start_year,
  p.floruit_end_year,
  p.dynasty_code,
  d.label_zh as dynasty_label_zh,
  d.label_en as dynasty_label_en,
  p.is_female,
  p.notes
from figure_data.persons p
left join figure_data.dynasties d on d.dynasty_code = p.dynasty_code
where p.id = :person_id
"""

PERSON_ALIASES_SQL = """
select
  alias_zh_hant,
  alias_zh_hans,
  alias_romanized,
  alias_type_label_zh,
  alias_type_label_en
from figure_data.person_aliases
where person_id = :person_id
order by alias_type_code nulls last, alias_zh_hant nulls last, alias_zh_hans nulls last, id
"""

PERSON_EXTERNAL_IDS_SQL = """
select source_name, external_id
from figure_data.person_external_ids
where person_id = :person_id
order by source_name, external_id
"""

PERSON_ENCOUNTER_COUNTS_SQL = """
select
  count(*) filter (where status = 'active') as active_count,
  count(*) filter (where status = 'active' and path_eligible = true) as path_eligible_count,
  count(*) filter (
    where status = 'active'
      and certainty_level = 'high'
  ) as high_certainty_count
from figure_data.encounters
where person_a_id = :person_id or person_b_id = :person_id
"""

PERSON_ENCOUNTERS_BASE_SQL = """
select
  e.id as encounter_id,
  case
    when e.person_a_id = :person_id then e.person_b_id
    else e.person_a_id
  end as other_person_id,
  coalesce(
    other_person.primary_name_zh_hant,
    other_person.primary_name_zh_hans,
    other_person.primary_name_romanized,
    other_person.id::text
  ) as other_person_name,
  other_person.birth_year as other_person_birth_year,
  other_person.death_year as other_person_death_year,
  e.encounter_kind,
  e.certainty_level,
  e.path_eligible,
  e.source_work_id,
  coalesce(sw.title_zh, sw.title_en) as source_title,
  e.pages,
  e.evidence_summary,
  e.status,
  e.reviewed_by,
  e.reviewed_at
from figure_data.encounters e
join figure_data.persons other_person
  on other_person.id = case
    when e.person_a_id = :person_id then e.person_b_id
    else e.person_a_id
  end
left join figure_data.source_works sw on sw.id = e.source_work_id
where e.person_a_id = :person_id or e.person_b_id = :person_id
"""


def get_person_detail(session: Session, person_id: UUID) -> PersonDetail:
    """Return one person detail or raise PersonDetailNotFoundError."""

    params = {"person_id": person_id}
    row = session.execute(text(PERSON_DETAIL_SQL), params).mappings().one_or_none()
    if row is None:
        raise PersonDetailNotFoundError(f"person was not found: {person_id}")

    alias_rows = session.execute(text(PERSON_ALIASES_SQL), params).mappings().all()
    external_id_rows = session.execute(text(PERSON_EXTERNAL_IDS_SQL), params).mappings().all()
    counts_row = session.execute(text(PERSON_ENCOUNTER_COUNTS_SQL), params).mappings().one_or_none()

    return PersonDetail(
        person_id=_uuid(row["person_id"]),
        primary_name_zh_hant=row["primary_name_zh_hant"],
        primary_name_zh_hans=row["primary_name_zh_hans"],
        primary_name_romanized=row["primary_name_romanized"],
        birth_year=row["birth_year"],
        death_year=row["death_year"],
        index_year=row["index_year"],
        floruit_start_year=row["floruit_start_year"],
        floruit_end_year=row["floruit_end_year"],
        dynasty_code=row["dynasty_code"],
        dynasty_label_zh=row["dynasty_label_zh"],
        dynasty_label_en=row["dynasty_label_en"],
        is_female=row["is_female"],
        notes=row["notes"],
        aliases=[
            PersonAliasDetail(
                alias_zh_hant=alias["alias_zh_hant"],
                alias_zh_hans=alias["alias_zh_hans"],
                alias_romanized=alias["alias_romanized"],
                alias_type_label_zh=alias["alias_type_label_zh"],
                alias_type_label_en=alias["alias_type_label_en"],
            )
            for alias in alias_rows
        ],
        external_ids=[
            PersonExternalIdDetail(
                source_name=external_id["source_name"],
                external_id=external_id["external_id"],
            )
            for external_id in external_id_rows
        ],
        encounter_summary=_encounter_counts(counts_row),
    )


def list_person_encounters(
    session: Session,
    person_id: UUID,
    filters: PersonEncounterFilters,
) -> list[PersonEncounterItem]:
    """Return reviewed encounters connected to one person."""

    where_clauses: list[str] = []
    params: dict[str, Any] = {
        "person_id": person_id,
        "limit": filters.limit,
        "offset": filters.offset,
    }
    if filters.status is not None:
        where_clauses.append("e.status = :status")
        params["status"] = filters.status
    if filters.path_eligible is not None:
        where_clauses.append("e.path_eligible = :path_eligible")
        params["path_eligible"] = filters.path_eligible
    if filters.certainty_level is not None:
        where_clauses.append("e.certainty_level = :certainty_level")
        params["certainty_level"] = filters.certainty_level
    if filters.encounter_kind is not None:
        where_clauses.append("e.encounter_kind = :encounter_kind")
        params["encounter_kind"] = filters.encounter_kind

    filters_sql = "".join(f"\n  and {clause}" for clause in where_clauses)
    statement = text(
        f"""
{PERSON_ENCOUNTERS_BASE_SQL}
{filters_sql}
order by e.reviewed_at desc, e.id
limit :limit offset :offset
"""
    )
    rows = session.execute(statement, params).mappings().all()
    return [
        PersonEncounterItem(
            encounter_id=_uuid(row["encounter_id"]),
            other_person_id=_uuid(row["other_person_id"]),
            other_person_name=row["other_person_name"],
            other_person_birth_year=row["other_person_birth_year"],
            other_person_death_year=row["other_person_death_year"],
            encounter_kind=row["encounter_kind"],
            certainty_level=row["certainty_level"],
            path_eligible=row["path_eligible"],
            source_work_id=row["source_work_id"],
            source_title=row["source_title"],
            pages=row["pages"],
            evidence_summary=row["evidence_summary"],
            status=row["status"],
            reviewed_by=row["reviewed_by"],
            reviewed_at=_datetime(row["reviewed_at"]),
        )
        for row in rows
    ]


def _encounter_counts(row: Any | None) -> PersonEncounterSummaryCounts:
    if row is None:
        return PersonEncounterSummaryCounts(
            active_count=0,
            path_eligible_count=0,
            high_certainty_count=0,
        )
    return PersonEncounterSummaryCounts(
        active_count=row["active_count"] or 0,
        path_eligible_count=row["path_eligible_count"] or 0,
        high_certainty_count=row["high_certainty_count"] or 0,
    )


def _uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
