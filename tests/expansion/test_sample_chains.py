from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from figure_data.expansion.sample_chains import ChainSampleFilters, list_chain_samples


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> "MappingResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return MappingResult(
            [
                edge_row(
                    "enc-1",
                    "person-a",
                    "person-b",
                    "許幾",
                    "韓琦",
                    "780",
                    "630",
                ),
                edge_row(
                    "enc-2",
                    "person-b",
                    "person-c",
                    "韓琦",
                    "歐陽修",
                    "630",
                    "1384",
                ),
            ]
        )


def edge_row(
    encounter_id: str,
    person_a_id: str,
    person_b_id: str,
    person_a_name: str,
    person_b_name: str,
    person_a_cbdb_id: str,
    person_b_cbdb_id: str,
) -> dict[str, Any]:
    return {
        "encounter_id": encounter_id,
        "person_a_id": person_a_id,
        "person_b_id": person_b_id,
        "person_a_name": person_a_name,
        "person_b_name": person_b_name,
        "person_a_cbdb_id": person_a_cbdb_id,
        "person_b_cbdb_id": person_b_cbdb_id,
        "evidence_summary": "有直接互动证据",
        "pages": "11905",
        "reviewed_at": datetime(2026, 6, 10, tzinfo=UTC),
    }


def test_list_chain_samples_builds_in_memory_paths() -> None:
    session = FakeSession()

    samples = list_chain_samples(
        session,  # type: ignore[arg-type]
        ChainSampleFilters(max_depth=2, limit=10),
    )

    assert samples[0].length == 1
    assert samples[0].people[0].display_name == "許幾"
    assert any(sample.length == 2 for sample in samples)
    two_hop = next(sample for sample in samples if sample.length == 2)
    assert [edge.encounter_id for edge in two_hop.edges] == ["enc-1", "enc-2"]
    statement = session.statements[0]
    assert "from figure_data.encounters e" in statement
    assert "e.status = 'active'" in statement
    assert "e.path_eligible = true" in statement
    assert "e.certainty_level = 'high'" in statement
    assert "e.encounter_kind = 'direct_interaction'" in statement


def test_list_chain_samples_validates_depth() -> None:
    session = FakeSession()

    samples = list_chain_samples(
        session,  # type: ignore[arg-type]
        ChainSampleFilters(max_depth=9, limit=10),
    )

    assert samples
    params = session.params[0]
    assert params is not None
    assert params["limit"] == 250
