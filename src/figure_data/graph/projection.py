from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.graph.types import GraphEncounter, GraphPerson, ProjectionDataset

PATH_ENCOUNTER_WHERE = """e.status = 'active'
and e.path_eligible = true
and e.certainty_level = 'high'
and e.encounter_kind = 'direct_interaction'"""

PATH_ENCOUNTER_SQL = f"""
select
    e.id::text as encounter_id,
    e.person_a_id::text as person_a_id,
    e.person_b_id::text as person_b_id,
    e.encounter_kind,
    e.certainty_level,
    e.source_work_id,
    e.pages,
    e.evidence_summary,
    e.reviewed_by,
    e.reviewed_at,
    e.created_at,
    e.updated_at
from figure_data.encounters e
where {PATH_ENCOUNTER_WHERE}
order by e.id
"""

GRAPH_PERSON_SQL = """
select
    p.id::text as person_id,
    p.primary_name_zh_hant as primary_name_hant,
    p.primary_name_zh_hans as primary_name_hans,
    p.primary_name_romanized,
    p.birth_year,
    p.death_year,
    p.index_year,
    p.dynasty_code,
    coalesce(array_agg(pe.external_id order by pe.external_id)
        filter (where pe.external_id is not null), array[]::text[]) as external_ids,
    min(pe.external_id) filter (where pe.source_name = 'cbdb') as cbdb_external_id
from figure_data.persons p
left join figure_data.person_external_ids pe on pe.person_id = p.id
where p.id = any(:person_ids)
group by p.id
order by p.id
"""


def load_projection_dataset(session: Session) -> ProjectionDataset:
    encounter_rows = session.execute(text(PATH_ENCOUNTER_SQL)).mappings().all()
    encounters = tuple(
        graph_encounter_from_row(cast(Mapping[str, Any], row)) for row in encounter_rows
    )
    person_ids = sorted(
        {encounter.start_person_id for encounter in encounters}
        | {encounter.end_person_id for encounter in encounters}
    )
    if not person_ids:
        return ProjectionDataset(people=(), encounters=())
    person_rows = session.execute(
        text(GRAPH_PERSON_SQL),
        {"person_ids": person_ids},
    ).mappings().all()
    people = tuple(graph_person_from_row(cast(Mapping[str, Any], row)) for row in person_rows)
    return ProjectionDataset(people=people, encounters=encounters)


def graph_person_from_row(row: Mapping[str, Any]) -> GraphPerson:
    external_ids = tuple(str(value) for value in row["external_ids"] if value)
    return GraphPerson(
        person_id=str(row["person_id"]),
        cbdb_external_id=_optional_text(row["cbdb_external_id"]),
        external_ids=external_ids,
        primary_name_hant=_optional_text(row["primary_name_hant"]),
        primary_name_hans=_optional_text(row["primary_name_hans"]),
        primary_name_romanized=_optional_text(row["primary_name_romanized"]),
        birth_year=row["birth_year"],
        death_year=row["death_year"],
        index_year=row["index_year"],
        dynasty_code=row["dynasty_code"],
    )


def graph_encounter_from_row(row: Mapping[str, Any]) -> GraphEncounter:
    person_a_id = str(row["person_a_id"])
    person_b_id = str(row["person_b_id"])
    start_person_id, end_person_id = sorted((person_a_id, person_b_id))
    return GraphEncounter(
        encounter_id=str(row["encounter_id"]),
        start_person_id=start_person_id,
        end_person_id=end_person_id,
        encounter_kind=str(row["encounter_kind"]),
        certainty_level=str(row["certainty_level"]),
        source_work_id=row["source_work_id"],
        pages=_optional_text(row["pages"]),
        evidence_summary=str(row["evidence_summary"]),
        reviewed_by=str(row["reviewed_by"]),
        reviewed_at=_iso_datetime(row["reviewed_at"]),
        created_at=_iso_datetime(row["created_at"]),
        updated_at=_iso_datetime(row["updated_at"]),
    )


def _iso_datetime(value: datetime) -> str:
    return value.isoformat()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None
