from figure_data.graph.formatting import format_chain_result
from figure_data.graph.types import ChainEdge, ChainLookupResult, ChainPath, ChainPerson


def test_format_chain_result_includes_person_id_and_encounter_id() -> None:
    path = ChainPath(
        people=(
            ChainPerson("person-a", "諸葛亮", 181, 234, "25403"),
            ChainPerson("person-b", "司馬懿", 178, 251, "21204"),
        ),
        edges=(
            ChainEdge("encounter-1", "direct_interaction", "high", "12a", "二人有直接互动"),
        ),
    )

    result = ChainLookupResult(
        source_person_id="person-a",
        target_person_id="person-b",
        max_depth=12,
        path=path,
    )
    lines = format_chain_result(result)

    assert lines[0] == "chain\tlength=1"
    assert "person-a" in lines[1]
    assert "encounter-1" in lines[2]


def test_format_chain_result_includes_no_path_endpoints() -> None:
    result = ChainLookupResult(
        source_person_id="person-a",
        target_person_id="person-b",
        max_depth=12,
        path=None,
    )

    assert format_chain_result(result) == ["no_path\tfrom=person-a\tto=person-b\tmax_depth=12"]
