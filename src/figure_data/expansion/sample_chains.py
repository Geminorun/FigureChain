from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.expansion.types import ChainSample, ChainSampleEdge, ChainSamplePerson


@dataclass(frozen=True)
class ChainSampleFilters:
    max_depth: int = 3
    limit: int = 20


type Graph = dict[str, list[tuple[ChainSampleEdge, ChainSamplePerson]]]


def list_chain_samples(session: Session, filters: ChainSampleFilters) -> list[ChainSample]:
    max_depth = min(max(filters.max_depth, 1), 3)
    edge_limit = max(filters.limit * 25, 250)
    rows = (
        session.execute(
            text(
                """
                select
                  e.id::text as encounter_id,
                  e.person_a_id::text,
                  e.person_b_id::text,
                  coalesce(
                    pa.primary_name_zh_hant,
                    pa.primary_name_zh_hans,
                    pa.primary_name_romanized,
                    e.person_a_id::text
                  ) as person_a_name,
                  coalesce(
                    pb.primary_name_zh_hant,
                    pb.primary_name_zh_hans,
                    pb.primary_name_romanized,
                    e.person_b_id::text
                  ) as person_b_name,
                  pae.external_id as person_a_cbdb_id,
                  pbe.external_id as person_b_cbdb_id,
                  e.evidence_summary,
                  e.pages,
                  e.reviewed_at
                from figure_data.encounters e
                left join figure_data.persons pa on pa.id = e.person_a_id
                left join figure_data.persons pb on pb.id = e.person_b_id
                left join figure_data.person_external_ids pae
                  on pae.person_id = e.person_a_id
                 and pae.source_name = 'cbdb'
                left join figure_data.person_external_ids pbe
                  on pbe.person_id = e.person_b_id
                 and pbe.source_name = 'cbdb'
                where e.status = 'active'
                  and e.path_eligible = true
                  and e.certainty_level = 'high'
                  and e.encounter_kind = 'direct_interaction'
                order by e.reviewed_at desc, e.id
                limit :limit
                """
            ),
            {"limit": edge_limit},
        )
        .mappings()
        .all()
    )
    graph, people_by_id = _build_graph([cast(Mapping[str, Any], row) for row in rows])
    samples = _walk_samples(graph, people_by_id, max_depth=max_depth)
    return samples[: filters.limit]


def _build_graph(rows: list[Mapping[str, Any]]) -> tuple[Graph, dict[str, ChainSamplePerson]]:
    graph: Graph = defaultdict(list)
    people_by_id: dict[str, ChainSamplePerson] = {}
    for row in rows:
        person_a = ChainSamplePerson(
            person_id=str(row["person_a_id"]),
            display_name=str(row["person_a_name"]),
            cbdb_external_id=_optional_text(row["person_a_cbdb_id"]),
        )
        person_b = ChainSamplePerson(
            person_id=str(row["person_b_id"]),
            display_name=str(row["person_b_name"]),
            cbdb_external_id=_optional_text(row["person_b_cbdb_id"]),
        )
        people_by_id[person_a.person_id] = person_a
        people_by_id[person_b.person_id] = person_b
        edge = ChainSampleEdge(
            encounter_id=str(row["encounter_id"]),
            person_a_id=person_a.person_id,
            person_b_id=person_b.person_id,
            evidence_summary=str(row["evidence_summary"]),
            pages=_optional_text(row["pages"]),
        )
        graph[person_a.person_id].append((edge, person_b))
        graph[person_b.person_id].append((edge, person_a))
    for neighbors in graph.values():
        neighbors.sort(key=lambda item: (item[1].display_name, item[0].encounter_id))
    return dict(graph), people_by_id


def _walk_samples(
    graph: Graph,
    people_by_id: dict[str, ChainSamplePerson],
    *,
    max_depth: int,
) -> list[ChainSample]:
    samples: list[ChainSample] = []
    for source_id in sorted(graph):
        source = people_by_id[source_id]
        _walk_from(
            graph,
            source,
            people=(source,),
            edges=(),
            visited={source.person_id},
            max_depth=max_depth,
            samples=samples,
        )
    samples.sort(
        key=lambda sample: (
            sample.length,
            ",".join(edge.encounter_id for edge in sample.edges),
            " -> ".join(person.display_name for person in sample.people),
        )
    )
    return _dedupe_undirected(samples)


def _walk_from(
    graph: Graph,
    current: ChainSamplePerson,
    *,
    people: tuple[ChainSamplePerson, ...],
    edges: tuple[ChainSampleEdge, ...],
    visited: set[str],
    max_depth: int,
    samples: list[ChainSample],
) -> None:
    if edges:
        samples.append(ChainSample(people=people, edges=edges))
    if len(edges) == max_depth:
        return
    for edge, next_person in graph.get(current.person_id, []):
        if next_person.person_id in visited:
            continue
        _walk_from(
            graph,
            next_person,
            people=people + (next_person,),
            edges=edges + (edge,),
            visited=visited | {next_person.person_id},
            max_depth=max_depth,
            samples=samples,
        )


def _dedupe_undirected(samples: list[ChainSample]) -> list[ChainSample]:
    seen: set[tuple[str, ...]] = set()
    output: list[ChainSample] = []
    for sample in samples:
        forward = tuple(person.person_id for person in sample.people)
        reverse = tuple(reversed(forward))
        key = min(forward, reverse)
        if key in seen:
            continue
        seen.add(key)
        output.append(sample)
    return output


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None
