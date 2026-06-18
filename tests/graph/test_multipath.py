from figure_data.graph.multipath import (
    build_multipath_cypher,
    certainty_levels_for_minimum,
    validate_multipath_limits,
)
from figure_data.graph.types import GraphPathError, MultiPathFilters


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
