from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Protocol, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.graph.batches import (
    get_latest_projection_batch,
    mark_projection_batch_validation,
)
from figure_data.graph.projection import PATH_ENCOUNTER_WHERE
from figure_data.graph.types import GraphProjectionBatchRecord
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

POSTGRES_PATH_ENCOUNTER_IDS_SQL = f"""
select e.id::text as encounter_id
from figure_data.encounters e
where {PATH_ENCOUNTER_WHERE}
order by e.id
"""

NEO4J_RELATIONSHIP_COUNT_CYPHER = """
match ()-[r]->()
where type(r) = 'ENCOUNTERED'
return count(r) as count
"""

NEO4J_PERSON_COUNT_CYPHER = """
match (p)
where 'FigurePerson' in labels(p)
return count(p) as count
"""

NEO4J_MISSING_PERSON_ID_CYPHER = """
match (p)
where 'FigurePerson' in labels(p)
and not 'person_id' in keys(p)
return count(p) as count
"""

NEO4J_MISSING_ENCOUNTER_ID_CYPHER = """
match ()-[r]->()
where type(r) = 'ENCOUNTERED'
and not 'encounter_id' in keys(r)
return count(r) as count
"""

NEO4J_ENCOUNTER_KIND_CYPHER = """
match ()-[r]->()
where type(r) = 'ENCOUNTERED'
and (not 'encounter_kind' in keys(r) or r.encounter_kind <> 'direct_interaction')
return count(r) as count
"""

NEO4J_CERTAINTY_LEVEL_CYPHER = """
match ()-[r]->()
where type(r) = 'ENCOUNTERED'
and (not 'certainty_level' in keys(r) or r.certainty_level <> 'high')
return count(r) as count
"""

NEO4J_ENCOUNTER_IDS_CYPHER = """
match ()-[r]->()
where type(r) = 'ENCOUNTERED'
and 'encounter_id' in keys(r)
return r.encounter_id as encounter_id
order by r.encounter_id
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
        NEO4J_RELATIONSHIP_COUNT_CYPHER,
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
        NEO4J_PERSON_COUNT_CYPHER,
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
            _neo4j_zero_check_or_skip(
                graph_session,
                "graph:missing_person_id",
                NEO4J_MISSING_PERSON_ID_CYPHER,
                should_skip=neo4j_person_count == 0,
            ),
            _neo4j_zero_check_or_skip(
                graph_session,
                "graph:missing_encounter_id",
                NEO4J_MISSING_ENCOUNTER_ID_CYPHER,
                should_skip=neo4j_relationship_count == 0,
            ),
            _neo4j_zero_check_or_skip(
                graph_session,
                "graph:encounter_kind",
                NEO4J_ENCOUNTER_KIND_CYPHER,
                should_skip=neo4j_relationship_count == 0,
            ),
            _neo4j_zero_check_or_skip(
                graph_session,
                "graph:certainty_level",
                NEO4J_CERTAINTY_LEVEL_CYPHER,
                should_skip=neo4j_relationship_count == 0,
            ),
        ]
    )

    checks.append(_check_encounter_ids_resolve(pg_session, graph_session, neo4j_relationship_count))
    latest_success, latest_failed, batch_check = _check_last_successful_projection_batch(pg_session)
    checks.append(batch_check)
    _record_projection_batch_validation(pg_session, checks, latest_success)
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


def _neo4j_zero_check_or_skip(
    neo4j_session: GraphReadSession,
    name: str,
    query: str,
    should_skip: bool,
) -> ValidationCheck:
    if should_skip:
        return ValidationCheck(name, True, "violations=0")
    return _neo4j_zero_check(neo4j_session, name, query)


def _check_encounter_ids_resolve(
    pg_session: Session,
    neo4j_session: GraphReadSession,
    neo4j_relationship_count: int,
) -> ValidationCheck:
    postgres_ids = _postgres_path_encounter_ids(pg_session)
    neo4j_ids = set() if neo4j_relationship_count == 0 else _neo4j_encounter_ids(neo4j_session)
    missing = postgres_ids - neo4j_ids
    unexpected = neo4j_ids - postgres_ids
    return ValidationCheck(
        "graph:encounters_resolve",
        not missing and not unexpected,
        f"postgres={len(postgres_ids)} neo4j={len(neo4j_ids)} "
        f"missing={len(missing)} unexpected={len(unexpected)}",
    )


def _postgres_path_encounter_ids(pg_session: Session) -> set[str]:
    rows = pg_session.execute(text(POSTGRES_PATH_ENCOUNTER_IDS_SQL)).mappings().all()
    return {str(row["encounter_id"]) for row in rows}


def _neo4j_encounter_ids(neo4j_session: GraphReadSession) -> set[str]:
    rows = neo4j_session.run(NEO4J_ENCOUNTER_IDS_CYPHER)
    return {str(row["encounter_id"]) for row in rows}


def _check_last_successful_projection_batch(
    pg_session: Session,
) -> tuple[
    GraphProjectionBatchRecord | None,
    GraphProjectionBatchRecord | None,
    ValidationCheck,
]:
    latest_success = get_latest_projection_batch(pg_session, status="succeeded")
    latest_failed = get_latest_projection_batch(pg_session, status="failed")
    if latest_success is None:
        if latest_failed is None:
            return (
                latest_success,
                latest_failed,
                ValidationCheck("graph:last_successful_batch", True, "batch=none"),
            )
        return (
            latest_success,
            latest_failed,
            ValidationCheck(
                "graph:last_successful_batch",
                False,
                _format_batch_detail(latest_success=latest_success, latest_failed=latest_failed),
            ),
        )
    if latest_failed is not None and latest_failed.started_at > latest_success.started_at:
        return (
            latest_success,
            latest_failed,
            ValidationCheck(
                "graph:last_successful_batch",
                False,
                _format_batch_detail(latest_success=latest_success, latest_failed=latest_failed),
            ),
        )
    return (
        latest_success,
        latest_failed,
        ValidationCheck(
            "graph:last_successful_batch",
            True,
            _format_batch_detail(latest_success=latest_success, latest_failed=latest_failed),
        ),
    )


def _format_batch_detail(
    *,
    latest_success: GraphProjectionBatchRecord | None,
    latest_failed: GraphProjectionBatchRecord | None,
) -> str:
    success = "none" if latest_success is None else latest_success.id
    failed = "none" if latest_failed is None else latest_failed.id
    return f"latest_success={success} latest_failed={failed}"


def _record_projection_batch_validation(
    pg_session: Session,
    checks: list[ValidationCheck],
    latest_success: GraphProjectionBatchRecord | None,
) -> None:
    if latest_success is None:
        return
    mark_projection_batch_validation(
        pg_session,
        batch_id=latest_success.id,
        validation_status="passed" if all(check.passed for check in checks) else "failed",
        validation_summary={check.name: check.detail for check in checks},
    )
