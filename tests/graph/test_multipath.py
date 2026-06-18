from collections.abc import Iterator, Mapping
from typing import Any, cast

from pytest import MonkeyPatch
from sqlalchemy.orm import Session

from figure_data.graph.multipath import (
    build_multipath_cypher,
    certainty_levels_for_minimum,
    find_multipath,
    quality_score_for_path,
    rank_paths,
    validate_multipath_limits,
)
from figure_data.graph.pathfinding import ChainEndpointInput
from figure_data.graph.types import (
    ChainEdge,
    ChainPath,
    ChainPerson,
    GraphPathError,
    MultiPathFilters,
)


def _person(person_id: str) -> ChainPerson:
    return ChainPerson(person_id, person_id, None, None, None)


def _edge(encounter_id: str, certainty: str, kind: str = "direct_interaction") -> ChainEdge:
    return ChainEdge(
        encounter_id=encounter_id,
        encounter_kind=kind,
        certainty_level=certainty,
        pages=None,
        evidence_summary="evidence",
    )


def test_validate_multipath_limits() -> None:
    assert validate_multipath_limits(max_depth=12, max_paths=5, extra_depth=1) == (12, 5, 1)


def test_validate_multipath_limits_rejects_broad_values() -> None:
    for kwargs in (
        {"max_depth": 21, "max_paths": 5, "extra_depth": 0},
        {"max_depth": 12, "max_paths": 21, "extra_depth": 0},
        {"max_depth": 12, "max_paths": 5, "extra_depth": 3},
    ):
        try:
            validate_multipath_limits(**kwargs)
        except GraphPathError:
            pass
        else:
            raise AssertionError(f"expected GraphPathError for {kwargs}")


def test_certainty_levels_for_minimum() -> None:
    assert certainty_levels_for_minimum("high") == ("high",)
    assert certainty_levels_for_minimum("medium") == ("high", "medium")
    assert certainty_levels_for_minimum("low") == ("high", "medium", "low")
    assert certainty_levels_for_minimum(None) == ("high",)


def test_build_multipath_cypher_has_filter_hooks_without_apoc() -> None:
    query = build_multipath_cypher(12, MultiPathFilters())

    assert "match path =" in query.lower()
    assert "ENCOUNTERED*1..12" in query
    assert "apoc" not in query.lower()
    assert "all(rel in relationships(path)" in query
    assert "single(other in nodes(path)" in query
    assert "limit $candidate_limit" in query


def test_quality_score_penalizes_weaker_edges() -> None:
    high = ChainPath(people=(_person("a"), _person("b")), edges=(_edge("e1", "high"),))
    medium = ChainPath(people=(_person("a"), _person("b")), edges=(_edge("e1", "medium"),))
    low = ChainPath(people=(_person("a"), _person("b")), edges=(_edge("e1", "low"),))

    assert quality_score_for_path(high) == 1.0
    assert quality_score_for_path(medium) == 0.9
    assert quality_score_for_path(low) == 0.75


def test_rank_paths_orders_by_length_score_and_hash() -> None:
    short = ChainPath(people=(_person("a"), _person("b")), edges=(_edge("e1", "high"),))
    long = ChainPath(
        people=(_person("a"), _person("c"), _person("b")),
        edges=(_edge("e2", "high"), _edge("e3", "high")),
    )

    ranked = rank_paths(
        source_person_id="a",
        target_person_id="b",
        max_depth=12,
        paths=[long, short],
        max_paths=5,
    )

    assert [item.length for item in ranked] == [1, 2]
    assert [item.rank for item in ranked] == [1, 2]
    assert ranked[0].path_id == "path-1"


class FakeResult:
    def __init__(self, rows: list[Mapping[str, object]]) -> None:
        self.rows = rows

    def __iter__(self) -> Iterator[Mapping[str, object]]:
        return iter(self.rows)

    def single(self) -> Mapping[str, object] | None:
        return self.rows[0] if self.rows else None


class FakeGraphSession:
    def __init__(self, rows: list[Mapping[str, object]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def run(self, query: str, parameters: dict[str, object] | None = None) -> FakeResult:
        self.calls.append((query, parameters))
        if "return p.person_id as person_id" in query:
            return FakeResult(
                [
                    {"person_id": "source"},
                    {"person_id": "target"},
                ]
            )
        return FakeResult(self.rows)


def test_find_multipath_returns_no_path(monkeypatch: MonkeyPatch) -> None:
    def resolve(pg_session: object, endpoint: ChainEndpointInput) -> Any:
        return type("Resolved", (), {"label": endpoint.label, "person_id": endpoint.label})()

    monkeypatch.setattr("figure_data.graph.multipath.resolve_endpoint", resolve)
    result = find_multipath(
        pg_session=cast(Session, object()),
        neo4j_session=FakeGraphSession([]),
        source=ChainEndpointInput("source", None, None, "source"),
        target=ChainEndpointInput("target", None, None, "target"),
        max_depth=12,
        max_paths=5,
        extra_depth=0,
        filters=MultiPathFilters(),
    )

    assert result.status == "no_path"
    assert result.paths == ()
