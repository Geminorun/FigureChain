from typing import Any

from figure_data.graph.validation import validate_graph


class PgScalarResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class PgMappingResult:
    def mappings(self) -> "PgMappingResult":
        return self

    def all(self) -> list[dict[str, str]]:
        return [{"encounter_id": "encounter-1"}]


class FakePgSession:
    def __init__(self) -> None:
        self.scalar_values = [1, 2, 0]
        self.statements: list[str] = []

    def execute(self, statement: Any, params: dict[str, object] | None = None) -> object:
        self.statements.append(str(statement))
        if "where e.id::text = any" in str(statement):
            return PgScalarResult(1)
        if "select e.id::text as encounter_id" in str(statement):
            return PgMappingResult()
        return PgScalarResult(self.scalar_values.pop(0))


class Neo4jScalarResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def single(self) -> dict[str, int]:
        return {"count": self.value}


class Neo4jMappingResult:
    def __iter__(self) -> object:
        return iter([{"encounter_id": "encounter-1"}])


class FakeNeo4jSession:
    def __init__(self) -> None:
        self.values = [1, 2, 0, 0, 0, 0]
        self.queries: list[str] = []

    def run(self, query: str, parameters: dict[str, object] | None = None) -> object:
        self.queries.append(query)
        if "return r.encounter_id as encounter_id" in query:
            return Neo4jMappingResult()
        return Neo4jScalarResult(self.values.pop(0))


def test_validate_graph_returns_expected_checks() -> None:
    checks = validate_graph(FakePgSession(), FakeNeo4jSession())  # type: ignore[arg-type]

    assert {check.name for check in checks} == {
        "graph:relationship_count",
        "graph:person_count",
        "graph:missing_person_id",
        "graph:missing_encounter_id",
        "graph:encounter_kind",
        "graph:certainty_level",
        "graph:encounters_resolve",
    }
    assert all(check.passed for check in checks)


def test_validate_graph_uses_path_encounter_rule() -> None:
    pg_session = FakePgSession()

    validate_graph(pg_session, FakeNeo4jSession())  # type: ignore[arg-type]

    assert "path_eligible = true" in pg_session.statements[0]
    assert "certainty_level = 'high'" in pg_session.statements[0]
    assert "encounter_kind = 'direct_interaction'" in pg_session.statements[0]
