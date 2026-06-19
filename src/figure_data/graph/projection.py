from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.encounters.validation import validate_encounters
from figure_data.graph.batches import (
    get_latest_projection_batch,
    mark_projection_batch_failed,
    mark_projection_batch_succeeded,
    start_projection_batch,
)
from figure_data.graph.types import (
    GraphEncounter,
    GraphPerson,
    GraphProjectionError,
    IncrementalProjectionStats,
    ProjectionDataset,
    ProjectionStats,
)


class GraphWriteSession(Protocol):
    def run(self, query: str, parameters: dict[str, object] | None = None) -> object: ...

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

CHANGED_ENCOUNTER_SQL = """
select e.id::text as encounter_id
from figure_data.encounters e
where (:source_watermark is null or e.updated_at >= :source_watermark)
and e.updated_at < :source_watermark_upper
order by e.updated_at, e.id
"""

SOURCE_WATERMARK_UPPER_SQL = """
select transaction_timestamp() as source_watermark_upper
"""

PATH_ENCOUNTER_BY_IDS_SQL = f"""
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
and e.id = any(:encounter_ids)
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

CLEAR_GRAPH_CYPHER = """
match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson)
delete r
with 1 as ignored
match (p:FigurePerson)
where not (p)--()
delete p
"""

CONSTRAINT_CYPHER = """
create constraint figure_person_person_id_unique if not exists
for (p:FigurePerson)
require p.person_id is unique
"""

PERSON_BATCH_CYPHER = """
unwind $rows as row
merge (p:FigurePerson {person_id: row.person_id})
set p.cbdb_external_id = row.cbdb_external_id,
    p.external_ids = row.external_ids,
    p.primary_name_hant = row.primary_name_hant,
    p.primary_name_hans = row.primary_name_hans,
    p.primary_name_romanized = row.primary_name_romanized,
    p.birth_year = row.birth_year,
    p.death_year = row.death_year,
    p.index_year = row.index_year,
    p.dynasty_code = row.dynasty_code,
    p.updated_at = row.updated_at
"""

ENCOUNTER_BATCH_CYPHER = """
unwind $rows as row
match (a:FigurePerson {person_id: row.start_person_id})
match (b:FigurePerson {person_id: row.end_person_id})
merge (a)-[r:ENCOUNTERED {encounter_id: row.encounter_id}]->(b)
set r.encounter_kind = row.encounter_kind,
    r.certainty_level = row.certainty_level,
    r.source_work_id = row.source_work_id,
    r.pages = row.pages,
    r.evidence_summary = row.evidence_summary,
    r.reviewed_by = row.reviewed_by,
    r.reviewed_at = row.reviewed_at,
    r.created_at = row.created_at,
    r.updated_at = row.updated_at
"""

DELETE_ENCOUNTER_CYPHER = """
match ()-[r:ENCOUNTERED {encounter_id: $encounter_id}]->()
delete r
"""


def sync_graph_rebuild(
    pg_session: Session,
    neo4j_session: GraphWriteSession,
    *,
    triggered_by: str = "cli",
) -> ProjectionStats:
    started_at = datetime.now(UTC)
    batch_id = start_projection_batch(
        pg_session,
        mode="rebuild",
        triggered_by=triggered_by,
        source_watermark=None,
    )
    try:
        failed_checks = [check for check in validate_encounters(pg_session) if not check.passed]
        if failed_checks:
            names = ",".join(check.name for check in failed_checks)
            raise GraphProjectionError(
                f"validate-encounters failed before graph projection: {names}"
            )

        dataset = load_projection_dataset(pg_session)
        neo4j_session.run(CLEAR_GRAPH_CYPHER)
        neo4j_session.run(CONSTRAINT_CYPHER)
        if not dataset.encounters:
            finished_at = datetime.now(UTC)
            stats = ProjectionStats(
                persons_projected=0,
                encounters_projected=0,
                relationships_projected=0,
                started_at=started_at,
                finished_at=finished_at,
            )
            mark_projection_batch_succeeded(
                pg_session,
                batch_id=batch_id,
                encounters_seen=0,
                persons_written=0,
                relationships_written=0,
                relationships_deleted=0,
            )
            return stats

        projection_time = started_at.isoformat()
        neo4j_session.run(
            PERSON_BATCH_CYPHER,
            {"rows": [_person_to_neo4j_row(person, projection_time) for person in dataset.people]},
        )
        neo4j_session.run(
            ENCOUNTER_BATCH_CYPHER,
            {"rows": [_encounter_to_neo4j_row(encounter) for encounter in dataset.encounters]},
        )
        finished_at = datetime.now(UTC)
        stats = ProjectionStats(
            persons_projected=len(dataset.people),
            encounters_projected=len(dataset.encounters),
            relationships_projected=len(dataset.encounters),
            started_at=started_at,
            finished_at=finished_at,
        )
        mark_projection_batch_succeeded(
            pg_session,
            batch_id=batch_id,
            encounters_seen=len(dataset.encounters),
            persons_written=len(dataset.people),
            relationships_written=len(dataset.encounters),
            relationships_deleted=0,
        )
        return stats
    except Exception as exc:
        mark_projection_batch_failed(
            pg_session,
            batch_id=batch_id,
            error_code="graph_projection_failed",
            error_message=str(exc),
        )
        raise


def sync_graph_incremental(
    pg_session: Session,
    neo4j_session: GraphWriteSession,
    *,
    triggered_by: str = "cli",
) -> IncrementalProjectionStats:
    latest_success = get_latest_projection_batch(pg_session, status="succeeded")
    source_watermark = None if latest_success is None else latest_success.source_watermark
    if source_watermark is None and latest_success is not None:
        source_watermark = latest_success.finished_at
    source_watermark_upper = _source_watermark_upper(pg_session)
    started_at = datetime.now(UTC)
    batch_id = start_projection_batch(
        pg_session,
        mode="incremental",
        triggered_by=triggered_by,
        source_watermark=source_watermark_upper,
    )
    try:
        changed_ids = _changed_encounter_ids(
            pg_session,
            source_watermark,
            source_watermark_upper,
        )
        for encounter_id in changed_ids:
            neo4j_session.run(DELETE_ENCOUNTER_CYPHER, {"encounter_id": encounter_id})

        dataset = load_projection_dataset_for_encounters(pg_session, changed_ids)
        if dataset.encounters:
            projection_time = started_at.isoformat()
            neo4j_session.run(
                PERSON_BATCH_CYPHER,
                {
                    "rows": [
                        _person_to_neo4j_row(person, projection_time)
                        for person in dataset.people
                    ]
                },
            )
            neo4j_session.run(
                ENCOUNTER_BATCH_CYPHER,
                {"rows": [_encounter_to_neo4j_row(encounter) for encounter in dataset.encounters]},
            )

        finished_at = datetime.now(UTC)
        stats = IncrementalProjectionStats(
            persons_written=len(dataset.people),
            encounters_seen=len(changed_ids),
            relationships_written=len(dataset.encounters),
            relationships_deleted=len(changed_ids),
            started_at=started_at,
            finished_at=finished_at,
        )
        mark_projection_batch_succeeded(
            pg_session,
            batch_id=batch_id,
            encounters_seen=stats.encounters_seen,
            persons_written=stats.persons_written,
            relationships_written=stats.relationships_written,
            relationships_deleted=stats.relationships_deleted,
        )
        return stats
    except Exception as exc:
        mark_projection_batch_failed(
            pg_session,
            batch_id=batch_id,
            error_code="graph_projection_failed",
            error_message=str(exc),
        )
        raise


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


def load_projection_dataset_for_encounters(
    session: Session,
    encounter_ids: list[str],
) -> ProjectionDataset:
    if not encounter_ids:
        return ProjectionDataset(people=(), encounters=())
    encounter_rows = (
        session.execute(
            text(PATH_ENCOUNTER_BY_IDS_SQL),
            {"encounter_ids": encounter_ids},
        )
        .mappings()
        .all()
    )
    encounters = tuple(
        graph_encounter_from_row(cast(Mapping[str, Any], row)) for row in encounter_rows
    )
    person_ids = sorted(
        {encounter.start_person_id for encounter in encounters}
        | {encounter.end_person_id for encounter in encounters}
    )
    if not person_ids:
        return ProjectionDataset(people=(), encounters=encounters)
    person_rows = session.execute(
        text(GRAPH_PERSON_SQL),
        {"person_ids": person_ids},
    ).mappings().all()
    people = tuple(graph_person_from_row(cast(Mapping[str, Any], row)) for row in person_rows)
    return ProjectionDataset(people=people, encounters=encounters)


def _changed_encounter_ids(
    session: Session,
    source_watermark: datetime | None,
    source_watermark_upper: datetime,
) -> list[str]:
    rows = (
        session.execute(
            text(CHANGED_ENCOUNTER_SQL),
            {
                "source_watermark": source_watermark,
                "source_watermark_upper": source_watermark_upper,
            },
        )
        .mappings()
        .all()
    )
    return [str(row["encounter_id"]) for row in rows]


def _source_watermark_upper(session: Session) -> datetime:
    value = session.execute(text(SOURCE_WATERMARK_UPPER_SQL)).scalar_one()
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


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


def _person_to_neo4j_row(person: GraphPerson, projection_time: str) -> dict[str, object]:
    return {
        "person_id": person.person_id,
        "cbdb_external_id": person.cbdb_external_id,
        "external_ids": list(person.external_ids),
        "primary_name_hant": person.primary_name_hant,
        "primary_name_hans": person.primary_name_hans,
        "primary_name_romanized": person.primary_name_romanized,
        "birth_year": person.birth_year,
        "death_year": person.death_year,
        "index_year": person.index_year,
        "dynasty_code": person.dynasty_code,
        "updated_at": projection_time,
    }


def _encounter_to_neo4j_row(encounter: GraphEncounter) -> dict[str, object]:
    return {
        "encounter_id": encounter.encounter_id,
        "start_person_id": encounter.start_person_id,
        "end_person_id": encounter.end_person_id,
        "encounter_kind": encounter.encounter_kind,
        "certainty_level": encounter.certainty_level,
        "source_work_id": encounter.source_work_id,
        "pages": encounter.pages,
        "evidence_summary": encounter.evidence_summary,
        "reviewed_by": encounter.reviewed_by,
        "reviewed_at": encounter.reviewed_at,
        "created_at": encounter.created_at,
        "updated_at": encounter.updated_at,
    }
