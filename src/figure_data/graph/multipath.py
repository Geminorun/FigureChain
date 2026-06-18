from __future__ import annotations

from typing import cast

from sqlalchemy.orm import Session

from figure_data.ai.chain_hash import compute_chain_hash
from figure_data.ai.prompts import get_prompt_definition
from figure_data.graph.pathfinding import (
    ChainEndpointInput,
    GraphPathSession,
    _chain_path_from_neo4j_path,
    _require_projected_endpoints,
    resolve_endpoint,
)
from figure_data.graph.types import (
    ChainPath,
    GraphPathError,
    MultiPathFilters,
    MultiPathLookupResult,
    RankedChainPath,
)

CANDIDATE_PATH_LIMIT = 200


def validate_multipath_limits(
    max_depth: int,
    max_paths: int,
    extra_depth: int,
) -> tuple[int, int, int]:
    if max_depth < 1 or max_depth > 20:
        raise GraphPathError("max_depth must be between 1 and 20 for multipath")
    if max_paths < 1 or max_paths > 20:
        raise GraphPathError("max_paths must be between 1 and 20")
    if extra_depth < 0 or extra_depth > 2:
        raise GraphPathError("extra_depth must be between 0 and 2")
    return max_depth, max_paths, extra_depth


def certainty_levels_for_minimum(minimum: str | None) -> tuple[str, ...]:
    if minimum in (None, "high"):
        return ("high",)
    if minimum == "medium":
        return ("high", "medium")
    if minimum == "low":
        return ("high", "medium", "low")
    raise GraphPathError(f"unsupported min_certainty_level: {minimum}")


def build_multipath_cypher(max_depth: int, filters: MultiPathFilters) -> str:
    depth, _, _ = validate_multipath_limits(max_depth, 1, 0)
    return f"""
match (source:FigurePerson {{person_id: $source_person_id}})
match (target:FigurePerson {{person_id: $target_person_id}})
match path = (source)-[:ENCOUNTERED*1..{depth}]-(target)
where all(node in nodes(path)
  where single(other in nodes(path)
    where elementId(other) = elementId(node)))
  and all(rel in relationships(path)
    where rel.certainty_level in $certainty_levels)
  and ($encounter_kinds = [] or all(rel in relationships(path)
    where rel.encounter_kind in $encounter_kinds))
  and ($exclude_encounter_ids = [] or none(rel in relationships(path)
    where rel.encounter_id in $exclude_encounter_ids))
  and ($source_work_ids = [] or all(rel in relationships(path)
    where rel.source_work_id in $source_work_ids))
  and ($exclude_person_ids = [] or none(node in nodes(path)[1..-1]
    where node.person_id in $exclude_person_ids))
  and ($intermediate_dynasty_codes = [] or all(node in nodes(path)[1..-1]
    where node.dynasty_code is null
      or node.dynasty_code in $intermediate_dynasty_codes))
  and ($intermediate_year_min is null or all(node in nodes(path)[1..-1]
    where node.index_year is null
      or node.index_year >= $intermediate_year_min))
  and ($intermediate_year_max is null or all(node in nodes(path)[1..-1]
    where node.index_year is null
      or node.index_year <= $intermediate_year_max))
with path, length(path) as path_length
order by path_length asc
limit $candidate_limit
with collect({{path: path, path_length: path_length}}) as candidates
with candidates,
  case
    when size(candidates) = 0 then null
    else candidates[0].path_length
  end as shortest_length
unwind candidates as candidate
with candidate, shortest_length
where shortest_length is not null and candidate.path_length <= shortest_length + $extra_depth
return candidate.path as path, shortest_length
"""


def quality_score_for_path(path: ChainPath) -> float:
    score = 1.0
    for edge in path.edges:
        if edge.certainty_level == "medium":
            score -= 0.10
        elif edge.certainty_level == "low":
            score -= 0.25
        if edge.encounter_kind != "direct_interaction":
            score -= 0.05
    return max(score, 0.0)


def high_certainty_edge_count(path: ChainPath) -> int:
    return sum(1 for edge in path.edges if edge.certainty_level == "high")


def _chain_hash_for_path(
    *,
    source_person_id: str,
    target_person_id: str,
    max_depth: int,
    path: ChainPath,
) -> str:
    prompt = get_prompt_definition("chain_explanation")
    return compute_chain_hash(
        source_person_id=source_person_id,
        target_person_id=target_person_id,
        max_depth=max_depth,
        encounter_ids=[edge.encounter_id for edge in path.edges],
        prompt_key=prompt.prompt_key,
        prompt_version=prompt.prompt_version,
        output_schema_version=prompt.output_schema_version,
        language="zh-Hans",
    )


def rank_paths(
    *,
    source_person_id: str,
    target_person_id: str,
    max_depth: int,
    paths: list[ChainPath],
    max_paths: int,
) -> tuple[RankedChainPath, ...]:
    candidates = [
        (
            path,
            quality_score_for_path(path),
            _chain_hash_for_path(
                source_person_id=source_person_id,
                target_person_id=target_person_id,
                max_depth=max_depth,
                path=path,
            ),
        )
        for path in paths
    ]
    ordered = sorted(
        candidates,
        key=lambda item: (
            item[0].length,
            -item[1],
            -high_certainty_edge_count(item[0]),
            item[2],
        ),
    )
    return tuple(
        RankedChainPath(
            rank=index,
            path_id=f"path-{index}",
            chain_hash=chain_hash,
            quality_score=score,
            path=path,
        )
        for index, (path, score, chain_hash) in enumerate(ordered[:max_paths], start=1)
    )


def _parameters(
    *,
    source_person_id: str,
    target_person_id: str,
    max_paths: int,
    extra_depth: int,
    filters: MultiPathFilters,
) -> dict[str, object]:
    return {
        "source_person_id": source_person_id,
        "target_person_id": target_person_id,
        "certainty_levels": list(certainty_levels_for_minimum(filters.min_certainty_level)),
        "encounter_kinds": list(filters.encounter_kinds),
        "exclude_person_ids": list(filters.exclude_person_ids),
        "exclude_encounter_ids": list(filters.exclude_encounter_ids),
        "source_work_ids": list(filters.source_work_ids),
        "intermediate_dynasty_codes": list(filters.intermediate_dynasty_codes),
        "intermediate_year_min": filters.intermediate_year_min,
        "intermediate_year_max": filters.intermediate_year_max,
        "extra_depth": extra_depth,
        "candidate_limit": max(CANDIDATE_PATH_LIMIT, max_paths),
    }


def find_multipath(
    pg_session: Session,
    neo4j_session: object,
    source: ChainEndpointInput,
    target: ChainEndpointInput,
    max_depth: int,
    max_paths: int,
    extra_depth: int,
    filters: MultiPathFilters,
) -> MultiPathLookupResult:
    depth, paths_limit, extra = validate_multipath_limits(max_depth, max_paths, extra_depth)
    graph_session = cast(GraphPathSession, neo4j_session)
    source_endpoint = resolve_endpoint(pg_session, source)
    target_endpoint = resolve_endpoint(pg_session, target)
    _require_projected_endpoints(
        graph_session,
        source_endpoint.person_id,
        target_endpoint.person_id,
    )
    rows = list(
        graph_session.run(
            build_multipath_cypher(depth, filters),
            _parameters(
                source_person_id=source_endpoint.person_id,
                target_person_id=target_endpoint.person_id,
                max_paths=paths_limit,
                extra_depth=extra,
                filters=filters,
            ),
        )
    )
    if not rows:
        return MultiPathLookupResult(
            source_person_id=source_endpoint.person_id,
            target_person_id=target_endpoint.person_id,
            max_depth=depth,
            max_paths=paths_limit,
            extra_depth=extra,
            filters=filters,
            shortest_length=None,
            paths=(),
        )
    chain_paths = [_chain_path_from_neo4j_path(row["path"]) for row in rows]
    shortest_length = min(path.length for path in chain_paths)
    ranked = rank_paths(
        source_person_id=source_endpoint.person_id,
        target_person_id=target_endpoint.person_id,
        max_depth=depth,
        paths=chain_paths,
        max_paths=paths_limit,
    )
    return MultiPathLookupResult(
        source_person_id=source_endpoint.person_id,
        target_person_id=target_endpoint.person_id,
        max_depth=depth,
        max_paths=paths_limit,
        extra_depth=extra,
        filters=filters,
        shortest_length=shortest_length,
        paths=ranked,
    )
