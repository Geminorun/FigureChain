from datetime import UTC, datetime
from typing import Any

from figure_data.graph.validation import validate_graph


class PgScalarResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class PgMappingResult:
    def __init__(self, encounter_id: str | None = "encounter-1") -> None:
        self.encounter_id = encounter_id

    def mappings(self) -> "PgMappingResult":
        return self

    def all(self) -> list[dict[str, str]]:
        if self.encounter_id is None:
            return []
        return [{"encounter_id": self.encounter_id}]


class PgBatchMappingResult:
    def __init__(self, row: dict[str, object] | None) -> None:
        self.row = row

    def mappings(self) -> "PgBatchMappingResult":
        return self

    def one_or_none(self) -> dict[str, object] | None:
        return self.row


class FakePgSession:
    def __init__(self) -> None:
        self.scalar_values = [1, 2, 0]
        self.statements: list[str] = []
        self.params: list[dict[str, object] | None] = []
        self.last_params: dict[str, object] = {}
        self.latest_succeeded_batch: dict[str, object] | None = None
        self.latest_failed_batch: dict[str, object] | None = None

    def execute(self, statement: Any, params: dict[str, object] | None = None) -> object:
        self.statements.append(str(statement))
        self.params.append(params)
        self.last_params = params or {}
        if "update figure_data.graph_projection_batches" in str(statement):
            return PgScalarResult(0)
        if "from figure_data.graph_projection_batches" in str(statement):
            status = None if params is None else params.get("status")
            row = (
                self.latest_succeeded_batch
                if status == "succeeded"
                else self.latest_failed_batch
            )
            return PgBatchMappingResult(row)
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
        "graph:last_successful_batch",
    }
    assert all(check.passed for check in checks)


def test_validate_graph_uses_path_encounter_rule() -> None:
    pg_session = FakePgSession()

    validate_graph(pg_session, FakeNeo4jSession())  # type: ignore[arg-type]

    assert "path_eligible = true" in pg_session.statements[0]
    assert "certainty_level = 'high'" in pg_session.statements[0]
    assert "encounter_kind = 'direct_interaction'" in pg_session.statements[0]


class StaleEdgePgSession(FakePgSession):
    def execute(self, statement: Any, params: dict[str, object] | None = None) -> object:
        self.statements.append(str(statement))
        if "from figure_data.graph_projection_batches" in str(statement):
            return super().execute(statement, params)
        if "select e.id::text as encounter_id" in str(statement):
            return PgMappingResult("current-encounter")
        return PgScalarResult(self.scalar_values.pop(0))


class StaleEdgeNeo4jSession(FakeNeo4jSession):
    def run(self, query: str, parameters: dict[str, object] | None = None) -> object:
        self.queries.append(query)
        if "return r.encounter_id as encounter_id" in query:
            return iter([{"encounter_id": "stale-encounter"}])
        return Neo4jScalarResult(self.values.pop(0))


def test_validate_graph_rejects_edges_outside_path_encounter_set() -> None:
    checks = validate_graph(
        StaleEdgePgSession(),  # type: ignore[arg-type]
        StaleEdgeNeo4jSession(),
    )

    resolve_check = next(check for check in checks if check.name == "graph:encounters_resolve")

    assert not resolve_check.passed
    assert "unexpected=1" in resolve_check.detail


class EmptyPathPgSession(FakePgSession):
    def __init__(self) -> None:
        super().__init__()
        self.scalar_values = [0, 0]

    def execute(self, statement: Any, params: dict[str, object] | None = None) -> object:
        self.statements.append(str(statement))
        if "from figure_data.graph_projection_batches" in str(statement):
            return super().execute(statement, params)
        if "select e.id::text as encounter_id" in str(statement):
            return PgMappingResult(None)
        return PgScalarResult(self.scalar_values.pop(0))


class EmptyGraphNeo4jSession(FakeNeo4jSession):
    def __init__(self) -> None:
        super().__init__()
        self.values = [0, 0]

    def run(self, query: str, parameters: dict[str, object] | None = None) -> object:
        self.queries.append(query)
        if "return r.encounter_id as encounter_id" in query:
            return iter([])
        return Neo4jScalarResult(self.values.pop(0))


def test_validate_graph_skips_property_queries_when_graph_is_empty() -> None:
    neo4j_session = EmptyGraphNeo4jSession()

    checks = validate_graph(
        EmptyPathPgSession(),  # type: ignore[arg-type]
        neo4j_session,
    )

    assert all(check.passed for check in checks)
    assert not any(":ENCOUNTERED" in query for query in neo4j_session.queries)
    assert not any("p.person_id" in query for query in neo4j_session.queries)


def _batch_row(
    *,
    batch_id: str,
    status: str,
    started_at: datetime,
    finished_at: datetime | None,
) -> dict[str, object]:
    return {
        "id": batch_id,
        "mode": "incremental",
        "status": status,
        "triggered_by": "cli",
        "source_watermark": None,
        "encounters_seen": 1,
        "relationships_written": 1,
        "relationships_deleted": 0,
        "persons_written": 2,
        "validation_status": "not_run",
        "validation_summary": {},
        "error_code": None,
        "error_message": None,
        "started_at": started_at,
        "finished_at": finished_at,
    }


def test_validate_graph_reports_missing_projection_batch() -> None:
    checks = validate_graph(FakePgSession(), FakeNeo4jSession())  # type: ignore[arg-type]

    batch_check = next(check for check in checks if check.name == "graph:last_successful_batch")

    assert batch_check.passed
    assert batch_check.detail == "batch=none"


def test_validate_graph_fails_when_failed_batch_is_newer_than_success() -> None:
    pg_session = FakePgSession()
    pg_session.latest_succeeded_batch = _batch_row(
        batch_id="success-batch",
        status="succeeded",
        started_at=datetime(2026, 6, 19, 8, tzinfo=UTC),
        finished_at=datetime(2026, 6, 19, 8, 1, tzinfo=UTC),
    )
    pg_session.latest_failed_batch = _batch_row(
        batch_id="failed-batch",
        status="failed",
        started_at=datetime(2026, 6, 19, 9, tzinfo=UTC),
        finished_at=datetime(2026, 6, 19, 9, 1, tzinfo=UTC),
    )

    checks = validate_graph(pg_session, FakeNeo4jSession())  # type: ignore[arg-type]

    batch_check = next(check for check in checks if check.name == "graph:last_successful_batch")
    assert not batch_check.passed
    assert "latest_success=success-batch" in batch_check.detail
    assert "latest_failed=failed-batch" in batch_check.detail


def test_validate_graph_records_validation_status_on_latest_successful_batch() -> None:
    pg_session = FakePgSession()
    pg_session.latest_succeeded_batch = _batch_row(
        batch_id="success-batch",
        status="succeeded",
        started_at=datetime(2026, 6, 19, 8, tzinfo=UTC),
        finished_at=datetime(2026, 6, 19, 8, 1, tzinfo=UTC),
    )

    validate_graph(pg_session, FakeNeo4jSession())  # type: ignore[arg-type]

    assert any(
        "update figure_data.graph_projection_batches" in statement
        for statement in pg_session.statements
    )
    assert pg_session.last_params["batch_id"] == "success-batch"
    assert pg_session.last_params["validation_status"] == "passed"
    assert "graph:relationship_count" in str(pg_session.last_params["validation_summary"])
