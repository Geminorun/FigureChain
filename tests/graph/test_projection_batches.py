from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from figure_data.graph.batches import (
    get_latest_projection_batch,
    mark_projection_batch_failed,
    mark_projection_batch_succeeded,
    mark_projection_batch_validation,
    start_projection_batch,
)

BATCH_ID = UUID("00000000-0000-0000-0000-000000000501")
STARTED_AT = datetime(2026, 6, 19, 8, 0, tzinfo=UTC)
FINISHED_AT = datetime(2026, 6, 19, 8, 1, tzinfo=UTC)


@dataclass
class ScalarResult:
    value: object

    def scalar_one(self) -> object:
        return self.value


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> MappingResult:
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []
        self.last_params: dict[str, Any] = {}

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> object:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params)
        self.last_params = params or {}
        if "returning id" in sql:
            return ScalarResult(BATCH_ID)
        if "from figure_data.graph_projection_batches" in sql:
            return MappingResult(
                [
                    {
                        "id": BATCH_ID,
                        "mode": "rebuild",
                        "status": "succeeded",
                        "triggered_by": "cli",
                        "source_watermark": None,
                        "encounters_seen": 10,
                        "relationships_written": 10,
                        "relationships_deleted": 0,
                        "persons_written": 12,
                        "validation_status": "passed",
                        "validation_summary": {"graph:relationship_count": "ok"},
                        "error_code": None,
                        "error_message": None,
                        "started_at": STARTED_AT,
                        "finished_at": FINISHED_AT,
                    }
                ]
            )
        return ScalarResult(None)


def test_start_projection_batch_inserts_running_record() -> None:
    session = FakeSession()

    batch_id = start_projection_batch(
        session,  # type: ignore[arg-type]
        mode="rebuild",
        triggered_by="cli",
        source_watermark=None,
    )

    assert batch_id == BATCH_ID
    assert "insert into figure_data.graph_projection_batches" in session.statements[0]
    assert session.last_params["mode"] == "rebuild"
    assert session.last_params["status"] == "running"
    assert session.last_params["triggered_by"] == "cli"


def test_mark_projection_batch_succeeded_records_counts() -> None:
    session = FakeSession()

    mark_projection_batch_succeeded(
        session,  # type: ignore[arg-type]
        batch_id=BATCH_ID,
        encounters_seen=10,
        persons_written=12,
        relationships_written=10,
        relationships_deleted=0,
        validation_status="passed",
        validation_summary={"graph:relationship_count": "postgres=10 neo4j=10"},
    )

    assert session.last_params["status"] == "succeeded"
    assert session.last_params["relationships_written"] == 10
    assert session.last_params["validation_summary"] == (
        '{"graph:relationship_count": "postgres=10 neo4j=10"}'
    )


def test_mark_projection_batch_failed_redacts_error_message() -> None:
    session = FakeSession()

    mark_projection_batch_failed(
        session,  # type: ignore[arg-type]
        batch_id=BATCH_ID,
        error_code="neo4j_error",
        error_message="bolt://user:secret@localhost failed",
    )

    assert session.last_params["status"] == "failed"
    assert "secret" not in session.last_params["error_message"]
    assert "[REDACTED]" in session.last_params["error_message"]


def test_mark_projection_batch_validation_records_summary() -> None:
    session = FakeSession()

    mark_projection_batch_validation(
        session,  # type: ignore[arg-type]
        batch_id=BATCH_ID,
        validation_status="passed",
        validation_summary={"graph:relationship_count": "postgres=10 neo4j=10"},
    )

    assert session.last_params["batch_id"] == BATCH_ID
    assert session.last_params["validation_status"] == "passed"
    assert session.last_params["validation_summary"] == (
        '{"graph:relationship_count": "postgres=10 neo4j=10"}'
    )


def test_get_latest_projection_batch_maps_record() -> None:
    record = get_latest_projection_batch(FakeSession())  # type: ignore[arg-type]

    assert record is not None
    assert record.id == str(BATCH_ID)
    assert record.status == "succeeded"
    assert record.relationships_written == 10
