from uuid import UUID

from pytest import MonkeyPatch, raises

from figure_data.graph.pathfinding import (
    ChainEndpointInput,
    build_shortest_path_cypher,
    resolve_endpoint,
    validate_max_depth,
)
from figure_data.graph.types import GraphPathError
from figure_data.search.person_search import PersonSearchResult


class FakePgSession:
    def execute(self, statement: object, params: dict[str, object] | None = None) -> object:
        class Result:
            def scalar_one_or_none(self) -> str | None:
                return "00000000-0000-0000-0000-000000000001"

        return Result()


def test_validate_max_depth_accepts_one_to_thirty() -> None:
    assert validate_max_depth(1) == 1
    assert validate_max_depth(30) == 30


def test_validate_max_depth_rejects_out_of_range_values() -> None:
    with raises(GraphPathError, match="max_depth must be between 1 and 30"):
        validate_max_depth(31)


def test_build_shortest_path_cypher_embeds_validated_integer_literal() -> None:
    query = build_shortest_path_cypher(12)

    assert "[:ENCOUNTERED*..12]" in query
    assert "$max_depth" not in query


def test_resolve_endpoint_prefers_person_id() -> None:
    person_id = UUID("00000000-0000-0000-0000-000000000001")

    resolved = resolve_endpoint(
        FakePgSession(),  # type: ignore[arg-type]
        ChainEndpointInput(label="from", person_id=person_id, cbdb_id=None, query=None),
    )

    assert resolved.person_id == str(person_id)


def test_resolve_endpoint_rejects_multiple_name_matches(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "figure_data.graph.pathfinding.search_people",
        lambda session, query, limit: [
            PersonSearchResult(
                person_id="person-1",
                primary_name_zh_hant="諸葛亮",
                primary_name_zh_hans="诸葛亮",
                primary_name_romanized=None,
                birth_year=None,
                death_year=None,
                index_year=None,
                dynasty_code=None,
                matching_aliases=[],
                external_ids=[],
            ),
            PersonSearchResult(
                person_id="person-2",
                primary_name_zh_hant="諸葛亮",
                primary_name_zh_hans="诸葛亮",
                primary_name_romanized=None,
                birth_year=None,
                death_year=None,
                index_year=None,
                dynasty_code=None,
                matching_aliases=[],
                external_ids=[],
            ),
        ],
    )

    with raises(GraphPathError, match="matched multiple people"):
        resolve_endpoint(
            FakePgSession(),  # type: ignore[arg-type]
            ChainEndpointInput(label="from", person_id=None, cbdb_id=None, query="诸葛亮"),
        )
