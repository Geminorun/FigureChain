from figure_data.graph.types import (
    ChainEdge,
    ChainPath,
    ChainPerson,
    MultiPathFilters,
    MultiPathLookupResult,
    RankedChainPath,
)


def _person(person_id: str) -> ChainPerson:
    return ChainPerson(
        person_id=person_id,
        display_name=person_id,
        birth_year=None,
        death_year=None,
        cbdb_external_id=None,
    )


def _edge(encounter_id: str, certainty_level: str = "high") -> ChainEdge:
    return ChainEdge(
        encounter_id=encounter_id,
        encounter_kind="direct_interaction",
        certainty_level=certainty_level,
        pages=None,
        evidence_summary="evidence",
    )


def test_ranked_chain_path_length_and_score() -> None:
    path = ChainPath(
        people=(_person("a"), _person("b")),
        edges=(_edge("e1"),),
    )
    ranked = RankedChainPath(
        rank=1,
        path_id="path-1",
        chain_hash="sha256:test",
        quality_score=1.0,
        path=path,
    )

    assert ranked.length == 1
    assert ranked.path.edges[0].encounter_id == "e1"


def test_multipath_lookup_result_no_path() -> None:
    result = MultiPathLookupResult(
        source_person_id="source",
        target_person_id="target",
        max_depth=12,
        max_paths=5,
        extra_depth=0,
        filters=MultiPathFilters(),
        shortest_length=None,
        paths=(),
    )

    assert result.status == "no_path"
    assert result.returned_paths == 0


def test_multipath_lookup_result_found() -> None:
    path = RankedChainPath(
        rank=1,
        path_id="path-1",
        chain_hash="sha256:test",
        quality_score=1.0,
        path=ChainPath(people=(_person("a"), _person("b")), edges=(_edge("e1"),)),
    )
    result = MultiPathLookupResult(
        source_person_id="source",
        target_person_id="target",
        max_depth=12,
        max_paths=5,
        extra_depth=0,
        filters=MultiPathFilters(),
        shortest_length=1,
        paths=(path,),
    )

    assert result.status == "found"
    assert result.returned_paths == 1
