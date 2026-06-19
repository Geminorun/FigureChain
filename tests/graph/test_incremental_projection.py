from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pytest import MonkeyPatch

from figure_data.graph.projection import sync_graph_incremental
from figure_data.graph.types import GraphProjectionError

BATCH_ID = UUID("00000000-0000-0000-0000-000000000501")
LOWER_WATERMARK = datetime(2026, 6, 19, 12, 0, tzinfo=UTC)
UPPER_WATERMARK = datetime(2026, 6, 19, 12, 5, tzinfo=UTC)


@dataclass(frozen=True)
class GraphCall:
    query: str
    parameters: dict[str, object] | None


class FakeResult:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        *,
        scalar_value: object | None = None,
    ) -> None:
        self._rows = rows
        self._scalar_value = scalar_value

    def mappings(self) -> FakeResult:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows

    def scalar_one(self) -> object:
        return self._scalar_value


class FakeNeo4jSession:
    def __init__(self) -> None:
        self.calls: list[GraphCall] = []

    def run(self, query: str, parameters: dict[str, object] | None = None) -> None:
        self.calls.append(GraphCall(query=query, parameters=parameters))


class FakePgSessionWithChangedPathEncounter:
    def __init__(self) -> None:
        self.params_seen: list[dict[str, Any]] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> FakeResult:
        self.params_seen.append(params or {})
        sql = str(statement)
        if "select transaction_timestamp()" in sql:
            return FakeResult([], scalar_value=UPPER_WATERMARK)
        if "select e.id::text as encounter_id" in sql and "where" in sql:
            return FakeResult([{"encounter_id": "encounter-1"}])
        if "from figure_data.encounters" in sql:
            return FakeResult([_encounter_row()])
        return FakeResult([_person_row("person-a"), _person_row("person-b")])


class FakePgSessionWithDowngradedEncounter:
    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> FakeResult:
        sql = str(statement)
        if "select transaction_timestamp()" in sql:
            return FakeResult([], scalar_value=UPPER_WATERMARK)
        if "select e.id::text as encounter_id" in sql and "where" in sql:
            return FakeResult([{"encounter_id": "encounter-1"}])
        if "from figure_data.encounters" in sql:
            return FakeResult([])
        return FakeResult([])


class FailingPgSession:
    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> FakeResult:
        sql = str(statement)
        if "select transaction_timestamp()" in sql:
            return FakeResult([], scalar_value=UPPER_WATERMARK)
        raise GraphProjectionError("postgresql://user:secret@localhost/db failed")


def test_incremental_sync_deletes_changed_relationship_before_upsert(
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_projection_batch(monkeypatch)
    neo4j = FakeNeo4jSession()

    stats = sync_graph_incremental(
        FakePgSessionWithChangedPathEncounter(),  # type: ignore[arg-type]
        neo4j,
        triggered_by="cli",
    )

    assert stats.relationships_deleted == 1
    assert stats.relationships_written == 1
    assert any("delete r" in call.query.lower() for call in neo4j.calls)
    assert any("merge (a)-[r:ENCOUNTERED" in call.query for call in neo4j.calls)


def test_incremental_sync_deletes_downgraded_encounter_without_upsert(
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_projection_batch(monkeypatch)
    neo4j = FakeNeo4jSession()

    stats = sync_graph_incremental(
        FakePgSessionWithDowngradedEncounter(),  # type: ignore[arg-type]
        neo4j,
        triggered_by="cli",
    )

    assert stats.relationships_deleted == 1
    assert stats.relationships_written == 0


def test_incremental_sync_records_failed_batch(monkeypatch: MonkeyPatch) -> None:
    events: list[dict[str, object]] = []
    monkeypatch.setattr(
        "figure_data.graph.projection.start_projection_batch",
        lambda *args, **kwargs: BATCH_ID,
    )
    monkeypatch.setattr(
        "figure_data.graph.projection.get_latest_projection_batch",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "figure_data.graph.projection.mark_projection_batch_failed",
        lambda *args, **kwargs: events.append(kwargs),
    )

    with pytest.raises(GraphProjectionError):
        sync_graph_incremental(FailingPgSession(), FakeNeo4jSession(), triggered_by="cli")  # type: ignore[arg-type]

    assert events[0]["error_code"] == "graph_projection_failed"


def test_incremental_sync_uses_stable_source_watermark_window(
    monkeypatch: MonkeyPatch,
) -> None:
    events: list[dict[str, object]] = []
    pg_session = FakePgSessionWithChangedPathEncounter()

    def record_started_batch(*args: object, **kwargs: object) -> UUID:
        events.append({"event": "start", **kwargs})
        return BATCH_ID

    monkeypatch.setattr(
        "figure_data.graph.projection.start_projection_batch",
        record_started_batch,
    )
    monkeypatch.setattr(
        "figure_data.graph.projection.mark_projection_batch_succeeded",
        lambda *args, **kwargs: events.append({"event": "success", **kwargs}),
    )
    monkeypatch.setattr(
        "figure_data.graph.projection.get_latest_projection_batch",
        lambda *args, **kwargs: type(
            "Batch",
            (),
            {"source_watermark": LOWER_WATERMARK, "finished_at": UPPER_WATERMARK},
        )(),
    )

    sync_graph_incremental(
        pg_session,  # type: ignore[arg-type]
        FakeNeo4jSession(),
        triggered_by="cli",
    )

    changed_query_params = next(
        params for params in pg_session.params_seen if "source_watermark" in params
    )
    assert changed_query_params["source_watermark"] == LOWER_WATERMARK
    assert changed_query_params["source_watermark_upper"] == UPPER_WATERMARK
    start_event = next(event for event in events if event["event"] == "start")
    assert start_event["source_watermark"] == UPPER_WATERMARK


def _patch_projection_batch(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "figure_data.graph.projection.start_projection_batch",
        lambda *args, **kwargs: BATCH_ID,
    )
    monkeypatch.setattr(
        "figure_data.graph.projection.mark_projection_batch_succeeded",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "figure_data.graph.projection.get_latest_projection_batch",
        lambda *args, **kwargs: None,
    )


def _encounter_row() -> dict[str, Any]:
    now = datetime(2026, 6, 19, tzinfo=UTC)
    return {
        "encounter_id": "encounter-1",
        "person_a_id": "person-a",
        "person_b_id": "person-b",
        "encounter_kind": "direct_interaction",
        "certainty_level": "high",
        "source_work_id": 1,
        "pages": "12a",
        "evidence_summary": "二人有直接互动",
        "reviewed_by": "lyl",
        "reviewed_at": now,
        "created_at": now,
        "updated_at": now,
    }


def _person_row(person_id: str) -> dict[str, Any]:
    return {
        "person_id": person_id,
        "primary_name_hant": "許幾",
        "primary_name_hans": "许几",
        "primary_name_romanized": "Xu Ji",
        "birth_year": None,
        "death_year": None,
        "index_year": None,
        "dynasty_code": None,
        "external_ids": ["780"],
        "cbdb_external_id": "780",
    }
