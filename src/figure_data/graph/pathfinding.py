from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.graph.types import (
    ChainEdge,
    ChainLookupResult,
    ChainPath,
    ChainPerson,
    GraphPathError,
    GraphPersonAmbiguousError,
    ResolvedEndpoint,
)
from figure_data.search.person_search import search_people


@dataclass(frozen=True)
class ChainEndpointInput:
    label: str
    person_id: UUID | None
    cbdb_id: str | None
    query: str | None


class GraphResult(Protocol):
    def single(self) -> Mapping[str, object] | None: ...

    def __iter__(self) -> Iterator[Mapping[str, object]]: ...


class GraphPathSession(Protocol):
    def run(self, query: str, parameters: dict[str, object] | None = None) -> GraphResult: ...


class Neo4jPathLike(Protocol):
    nodes: Iterable[Mapping[str, object]]
    relationships: Iterable[Mapping[str, object]]


def validate_max_depth(max_depth: int) -> int:
    if max_depth < 1 or max_depth > 30:
        raise GraphPathError("max_depth must be between 1 and 30")
    return max_depth


def build_shortest_path_cypher(max_depth: int) -> str:
    depth = validate_max_depth(max_depth)
    return f"""
match (source:FigurePerson {{person_id: $source_person_id}})
match (target:FigurePerson {{person_id: $target_person_id}})
match path = shortestPath((source)-[:ENCOUNTERED*..{depth}]-(target))
return path
"""


def resolve_endpoint(pg_session: Session, endpoint: ChainEndpointInput) -> ResolvedEndpoint:
    if endpoint.person_id is not None:
        return ResolvedEndpoint(endpoint.label, str(endpoint.person_id))
    if endpoint.cbdb_id:
        person_id = _resolve_cbdb_id(pg_session, endpoint.cbdb_id)
        if person_id is None:
            raise GraphPathError(f"{endpoint.label} cbdb_id did not match a person")
        return ResolvedEndpoint(endpoint.label, person_id)
    if endpoint.query:
        matches = search_people(pg_session, endpoint.query, limit=5)
        if len(matches) == 0:
            raise GraphPathError(f"{endpoint.label} name did not match a person")
        if len(matches) > 1:
            raise GraphPersonAmbiguousError(
                label=endpoint.label,
                candidates=[match.person_id for match in matches],
            )
        return ResolvedEndpoint(endpoint.label, matches[0].person_id)
    raise GraphPathError(f"{endpoint.label} person input is required")


def find_chain(
    pg_session: Session,
    neo4j_session: object,
    source: ChainEndpointInput,
    target: ChainEndpointInput,
    max_depth: int,
) -> ChainLookupResult:
    depth = validate_max_depth(max_depth)
    graph_session = cast(GraphPathSession, neo4j_session)
    source_endpoint = resolve_endpoint(pg_session, source)
    target_endpoint = resolve_endpoint(pg_session, target)
    _require_projected_endpoints(
        graph_session,
        source_endpoint.person_id,
        target_endpoint.person_id,
    )
    query = build_shortest_path_cypher(depth)
    record = graph_session.run(
        query,
        {
            "source_person_id": source_endpoint.person_id,
            "target_person_id": target_endpoint.person_id,
        },
    ).single()
    if record is None:
        return ChainLookupResult(
            source_person_id=source_endpoint.person_id,
            target_person_id=target_endpoint.person_id,
            max_depth=depth,
            path=None,
        )
    return ChainLookupResult(
        source_person_id=source_endpoint.person_id,
        target_person_id=target_endpoint.person_id,
        max_depth=depth,
        path=_chain_path_from_neo4j_path(record["path"]),
    )


def _resolve_cbdb_id(pg_session: Session, cbdb_id: str) -> str | None:
    result = pg_session.execute(
        text(
            """
            select person_id::text
            from figure_data.person_external_ids
            where source_name = 'cbdb'
            and external_id = :external_id
            """
        ),
        {"external_id": cbdb_id},
    )
    return result.scalar_one_or_none()


def _require_projected_endpoints(
    neo4j_session: GraphPathSession,
    source_person_id: str,
    target_person_id: str,
) -> None:
    rows = neo4j_session.run(
        """
        match (p:FigurePerson)
        where p.person_id in $person_ids
        return p.person_id as person_id
        """,
        {"person_ids": [source_person_id, target_person_id]},
    )
    projected = {str(row["person_id"]) for row in rows}
    missing = [
        person_id
        for person_id in (source_person_id, target_person_id)
        if person_id not in projected
    ]
    if missing:
        raise GraphPathError(
            "endpoint person is not projected to Neo4j; run sync-graph --rebuild: "
            + ", ".join(missing)
        )


def _chain_path_from_neo4j_path(path: object) -> ChainPath:
    path_like = cast(Neo4jPathLike, path)
    nodes = list(path_like.nodes)
    relationships = list(path_like.relationships)
    people = tuple(_chain_person_from_node(node) for node in nodes)
    edges = tuple(_chain_edge_from_relationship(relationship) for relationship in relationships)
    return ChainPath(people=people, edges=edges)


def _chain_person_from_node(props: Mapping[str, object]) -> ChainPerson:
    name = (
        props.get("primary_name_hant")
        or props.get("primary_name_hans")
        or props.get("primary_name_romanized")
        or props["person_id"]
    )
    return ChainPerson(
        person_id=str(props["person_id"]),
        display_name=str(name),
        birth_year=_optional_int(props.get("birth_year")),
        death_year=_optional_int(props.get("death_year")),
        cbdb_external_id=_optional_text(props.get("cbdb_external_id")),
    )


def _chain_edge_from_relationship(props: Mapping[str, object]) -> ChainEdge:
    missing = [
        key
        for key in ("encounter_id", "encounter_kind", "certainty_level", "evidence_summary")
        if props.get(key) is None
    ]
    if missing:
        raise GraphPathError(
            "Neo4j edge is missing required properties; run sync-graph --rebuild: "
            + ", ".join(missing)
        )
    return ChainEdge(
        encounter_id=str(props["encounter_id"]),
        encounter_kind=str(props["encounter_kind"]),
        certainty_level=str(props["certainty_level"]),
        pages=_optional_text(props.get("pages")),
        evidence_summary=str(props["evidence_summary"]),
    )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return int(str(value))


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None
