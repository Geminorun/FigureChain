from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Protocol, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.graph.projection import PATH_ENCOUNTER_WHERE
from figure_data.validation.report import ValidationCheck

POSTGRES_RELATIONSHIP_COUNT_SQL = f"""
select count(*)
from figure_data.encounters e
where {PATH_ENCOUNTER_WHERE}
"""

POSTGRES_PERSON_COUNT_SQL = f"""
select count(distinct person_id)
from (
    select e.person_a_id as person_id
    from figure_data.encounters e
    where {PATH_ENCOUNTER_WHERE}
    union
    select e.person_b_id as person_id
    from figure_data.encounters e
    where {PATH_ENCOUNTER_WHERE}
) people
"""

POSTGRES_SAMPLE_ENCOUNTER_IDS_SQL = f"""
select e.id::text as encounter_id
from figure_data.encounters e
where {PATH_ENCOUNTER_WHERE}
order by e.id
limit :limit
"""

POSTGRES_RESOLVE_ENCOUNTERS_SQL = """
select count(*)
from figure_data.encounters e
where e.id::text = any(:encounter_ids)
"""


class GraphResult(Protocol):
    def single(self) -> Mapping[str, object]: ...

    def __iter__(self) -> Iterator[Mapping[str, object]]: ...


class GraphReadSession(Protocol):
    def run(self, query: str, parameters: dict[str, object] | None = None) -> GraphResult: ...


def validate_graph(
    pg_session: Session,
    neo4j_session: object,
    sample_limit: int = 50,
) -> list[ValidationCheck]:
    graph_session = cast(GraphReadSession, neo4j_session)
    checks: list[ValidationCheck] = []
    postgres_relationship_count = _pg_scalar(pg_session, POSTGRES_RELATIONSHIP_COUNT_SQL)
    neo4j_relationship_count = _neo4j_count(
        graph_session,
        "match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson) return count(r) as count",
    )
    checks.append(
        ValidationCheck(
            "graph:relationship_count",
            postgres_relationship_count == neo4j_relationship_count,
            f"postgres={postgres_relationship_count} neo4j={neo4j_relationship_count}",
        )
    )

    postgres_person_count = _pg_scalar(pg_session, POSTGRES_PERSON_COUNT_SQL)
    neo4j_person_count = _neo4j_count(
        graph_session,
        "match (p:FigurePerson) return count(p) as count",
    )
    checks.append(
        ValidationCheck(
            "graph:person_count",
            postgres_person_count == neo4j_person_count,
            f"postgres={postgres_person_count} neo4j={neo4j_person_count}",
        )
    )

    checks.extend(
        [
            _neo4j_zero_check(
                graph_session,
                "graph:missing_person_id",
                "match (p:FigurePerson) where p.person_id is null return count(p) as count",
            ),
            _neo4j_zero_check(
                graph_session,
                "graph:missing_encounter_id",
                "match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson) "
                "where r.encounter_id is null return count(r) as count",
            ),
            _neo4j_zero_check(
                graph_session,
                "graph:encounter_kind",
                "match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson) "
                "where r.encounter_kind <> 'direct_interaction' return count(r) as count",
            ),
            _neo4j_zero_check(
                graph_session,
                "graph:certainty_level",
                "match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson) "
                "where r.certainty_level <> 'high' return count(r) as count",
            ),
        ]
    )

    checks.append(_check_encounter_ids_resolve(pg_session, graph_session, sample_limit))
    return checks


def _pg_scalar(pg_session: Session, sql: str, params: dict[str, object] | None = None) -> int:
    return int(pg_session.execute(text(sql), params or {}).scalar_one())


def _neo4j_count(neo4j_session: GraphReadSession, query: str) -> int:
    record = neo4j_session.run(query).single()
    count = record["count"]
    if isinstance(count, int):
        return count
    return int(str(count))


def _neo4j_zero_check(
    neo4j_session: GraphReadSession,
    name: str,
    query: str,
) -> ValidationCheck:
    count = _neo4j_count(neo4j_session, query)
    return ValidationCheck(name, count == 0, f"violations={count}")


def _check_encounter_ids_resolve(
    pg_session: Session,
    neo4j_session: GraphReadSession,
    sample_limit: int,
) -> ValidationCheck:
    rows = neo4j_session.run(
        "match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson) "
        "where r.encounter_id is not null "
        "return r.encounter_id as encounter_id "
        "order by r.encounter_id "
        "limit $limit",
        {"limit": sample_limit},
    )
    encounter_ids = [str(row["encounter_id"]) for row in rows]
    if not encounter_ids:
        return ValidationCheck("graph:encounters_resolve", True, "sampled=0 missing=0")
    resolved = _pg_scalar(
        pg_session,
        POSTGRES_RESOLVE_ENCOUNTERS_SQL,
        {"encounter_ids": encounter_ids},
    )
    missing = len(encounter_ids) - resolved
    return ValidationCheck(
        "graph:encounters_resolve",
        missing == 0,
        f"sampled={len(encounter_ids)} missing={missing}",
    )
