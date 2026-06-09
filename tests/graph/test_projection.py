from datetime import UTC, datetime
from typing import Any

from pytest import MonkeyPatch

from figure_data.graph.projection import (
    CLEAR_GRAPH_CYPHER,
    CONSTRAINT_CYPHER,
    ENCOUNTER_BATCH_CYPHER,
    PATH_ENCOUNTER_WHERE,
    PERSON_BATCH_CYPHER,
    graph_encounter_from_row,
    graph_person_from_row,
    load_projection_dataset,
    sync_graph_rebuild,
)
from figure_data.graph.types import GraphEncounter, GraphPerson, ProjectionDataset


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> "FakeResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> FakeResult:
        self.statements.append(str(statement))
        if "from figure_data.encounters" in str(statement):
            return FakeResult(
                [
                    {
                        "encounter_id": "00000000-0000-0000-0000-000000000001",
                        "person_a_id": "00000000-0000-0000-0000-0000000000aa",
                        "person_b_id": "00000000-0000-0000-0000-0000000000bb",
                        "encounter_kind": "direct_interaction",
                        "certainty_level": "high",
                        "source_work_id": 1,
                        "pages": "12a",
                        "evidence_summary": "二人有直接互动",
                        "reviewed_by": "lyl",
                        "reviewed_at": datetime(2026, 6, 9, tzinfo=UTC),
                        "created_at": datetime(2026, 6, 9, tzinfo=UTC),
                        "updated_at": datetime(2026, 6, 9, tzinfo=UTC),
                    }
                ]
            )
        return FakeResult(
            [
                {
                    "person_id": "00000000-0000-0000-0000-0000000000aa",
                    "primary_name_hant": "諸葛亮",
                    "primary_name_hans": "诸葛亮",
                    "primary_name_romanized": "Zhuge Liang",
                    "birth_year": 181,
                    "death_year": 234,
                    "index_year": 220,
                    "dynasty_code": 30,
                    "external_ids": ["25403"],
                    "cbdb_external_id": "25403",
                },
                {
                    "person_id": "00000000-0000-0000-0000-0000000000bb",
                    "primary_name_hant": "司馬懿",
                    "primary_name_hans": "司马懿",
                    "primary_name_romanized": "Sima Yi",
                    "birth_year": 178,
                    "death_year": 251,
                    "index_year": 230,
                    "dynasty_code": 30,
                    "external_ids": ["21204"],
                    "cbdb_external_id": "21204",
                },
            ]
        )


def test_path_encounter_where_matches_path_edge_rule() -> None:
    assert "status = 'active'" in PATH_ENCOUNTER_WHERE
    assert "path_eligible = true" in PATH_ENCOUNTER_WHERE
    assert "certainty_level = 'high'" in PATH_ENCOUNTER_WHERE
    assert "encounter_kind = 'direct_interaction'" in PATH_ENCOUNTER_WHERE


def test_graph_person_from_row_normalizes_external_ids() -> None:
    person = graph_person_from_row(
        {
            "person_id": "person-1",
            "primary_name_hant": "諸葛亮",
            "primary_name_hans": "诸葛亮",
            "primary_name_romanized": None,
            "birth_year": 181,
            "death_year": 234,
            "index_year": 220,
            "dynasty_code": 30,
            "external_ids": ["25403", None, ""],
            "cbdb_external_id": "25403",
        }
    )

    assert person.person_id == "person-1"
    assert person.external_ids == ("25403",)
    assert person.cbdb_external_id == "25403"


def test_graph_encounter_from_row_sorts_relationship_direction() -> None:
    encounter = graph_encounter_from_row(
        {
            "encounter_id": "encounter-1",
            "person_a_id": "b-person",
            "person_b_id": "a-person",
            "encounter_kind": "direct_interaction",
            "certainty_level": "high",
            "source_work_id": None,
            "pages": "12a",
            "evidence_summary": "二人有直接互动",
            "reviewed_by": "lyl",
            "reviewed_at": datetime(2026, 6, 9, tzinfo=UTC),
            "created_at": datetime(2026, 6, 9, tzinfo=UTC),
            "updated_at": datetime(2026, 6, 9, tzinfo=UTC),
        }
    )

    assert encounter.start_person_id == "a-person"
    assert encounter.end_person_id == "b-person"


def test_load_projection_dataset_uses_only_path_encounters() -> None:
    session = FakeSession()

    dataset = load_projection_dataset(session)  # type: ignore[arg-type]

    assert len(dataset.people) == 2
    assert len(dataset.encounters) == 1
    assert "figure_data.encounters" in session.statements[0]
    assert PATH_ENCOUNTER_WHERE in session.statements[0]


class FakeGraphSession:
    def __init__(self) -> None:
        self.queries: list[tuple[str, dict[str, object] | None]] = []

    def run(self, query: str, parameters: dict[str, object] | None = None) -> None:
        self.queries.append((query, parameters))


def test_sync_graph_rebuild_clears_only_figurechain_graph() -> None:
    assert "match (:FigurePerson)-[r:ENCOUNTERED]-(:FigurePerson)" in CLEAR_GRAPH_CYPHER
    assert "delete r" in CLEAR_GRAPH_CYPHER
    assert "detach delete" not in CLEAR_GRAPH_CYPHER.lower()


def test_sync_graph_rebuild_writes_people_and_relationships(
    monkeypatch: MonkeyPatch,
) -> None:
    graph_session = FakeGraphSession()
    dataset = ProjectionDataset(
        people=(
            GraphPerson(
                person_id="person-a",
                cbdb_external_id="25403",
                external_ids=("25403",),
                primary_name_hant="諸葛亮",
                primary_name_hans="诸葛亮",
                primary_name_romanized="Zhuge Liang",
                birth_year=181,
                death_year=234,
                index_year=220,
                dynasty_code=30,
            ),
        ),
        encounters=(
            GraphEncounter(
                encounter_id="encounter-1",
                start_person_id="person-a",
                end_person_id="person-b",
                encounter_kind="direct_interaction",
                certainty_level="high",
                source_work_id=1,
                pages="12a",
                evidence_summary="二人有直接互动",
                reviewed_by="lyl",
                reviewed_at="2026-06-09T00:00:00+00:00",
                created_at="2026-06-09T00:00:00+00:00",
                updated_at="2026-06-09T00:00:00+00:00",
            ),
        ),
    )
    monkeypatch.setattr(
        "figure_data.graph.projection.load_projection_dataset",
        lambda session: dataset,
    )
    monkeypatch.setattr("figure_data.graph.projection.validate_encounters", lambda session: [])

    stats = sync_graph_rebuild(object(), graph_session)  # type: ignore[arg-type]

    assert stats.persons_projected == 1
    assert stats.encounters_projected == 1
    assert stats.relationships_projected == 1
    queries = [query for query, _params in graph_session.queries]
    assert CLEAR_GRAPH_CYPHER in queries
    assert CONSTRAINT_CYPHER in queries
    assert PERSON_BATCH_CYPHER in queries
    assert ENCOUNTER_BATCH_CYPHER in queries
