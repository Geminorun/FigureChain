from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.orm import Session, sessionmaker

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import AdminGraphOperationRequest, AdminGraphSyncRequest
from figure_chain.services.admin_graph import AdminGraphService
from figure_data.admin.operations import AdminOperationCreate, AdminOperationRecord
from figure_data.graph.types import (
    GraphProjectionBatchRecord,
    IncrementalProjectionStats,
    ProjectionStats,
)
from figure_data.validation.report import ValidationCheck

OPERATION_ID = UUID("00000000-0000-0000-0000-000000000701")
NOW = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)


class FakeBackgroundTasks:
    def __init__(self) -> None:
        self.calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    def add_task(self, func: object, *args: object, **kwargs: object) -> None:
        self.calls.append((func, args, kwargs))


def batch(batch_id: str, status: str) -> GraphProjectionBatchRecord:
    return GraphProjectionBatchRecord(
        id=batch_id,
        mode="rebuild",
        status=status,
        triggered_by="local",
        source_watermark=None,
        encounters_seen=10,
        relationships_written=10,
        relationships_deleted=0,
        persons_written=12,
        validation_status="passed",
        validation_summary={"graph:relationship_count": "postgres=10 neo4j=10"},
        error_code=None,
        error_message=None,
        started_at=NOW,
        finished_at=NOW + timedelta(minutes=1),
    )


def operation_record(
    *,
    status: str = "queued",
    operation_type: str = "sync_graph_rebuild",
    started_at: datetime | None = None,
) -> AdminOperationRecord:
    return AdminOperationRecord(
        id=OPERATION_ID,
        operation_type=operation_type,
        actor="local",
        status=status,
        request_payload={},
        result_summary={},
        error_message=None,
        related_resource_type="graph_projection_batch",
        related_resource_id=None,
        started_at=started_at,
        finished_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def test_graph_status_includes_latest_batches_and_stale_operations() -> None:
    stale = operation_record(status="running", started_at=NOW - timedelta(hours=1))

    service = AdminGraphService(
        cast(Session, object()),
        session_factory=cast(sessionmaker[Session], object()),
        neo4j_session=object(),
        background_tasks=FakeBackgroundTasks(),
        latest_batch_fn=lambda session, status: batch(f"{status}-batch", status or "succeeded"),
        count_encounters_fn=lambda session, *, path_eligible: 3 if path_eligible else 5,
        list_operations_fn=lambda session, **kwargs: [stale],
        now_fn=lambda: NOW,
    )

    response = service.get_status()

    assert response.latest_success is not None
    assert response.latest_success.id == "succeeded-batch"
    assert response.latest_failed is not None
    assert response.latest_failed.id == "failed-batch"
    assert response.active_encounter_count == 5
    assert response.path_eligible_encounter_count == 3
    assert response.stale_running_operations[0].operation_id == OPERATION_ID


def test_validate_encounters_creates_operation_and_background_task() -> None:
    background_tasks = FakeBackgroundTasks()
    created: list[AdminOperationCreate] = []

    def create_operation(session: object, operation: AdminOperationCreate) -> AdminOperationRecord:
        created.append(operation)
        return operation_record(operation_type=operation.operation_type)

    service = AdminGraphService(
        cast(Session, object()),
        session_factory=cast(sessionmaker[Session], object()),
        neo4j_session=object(),
        background_tasks=background_tasks,
        create_operation_fn=create_operation,
        validate_encounters_fn=lambda session: [
            ValidationCheck("encounters:no_self_loops", True, "violations=0")
        ],
    )

    response = service.start_validate_encounters(AdminGraphOperationRequest(actor="local"))

    assert created[0].operation_type == "validate_encounters"
    assert created[0].request_payload == {"actor": "local"}
    assert response.operation_id == OPERATION_ID
    assert response.preview == "figure-data validate-encounters"
    assert len(background_tasks.calls) == 1


def test_sync_graph_rebuild_creates_operation_with_cli_preview() -> None:
    background_tasks = FakeBackgroundTasks()
    created: list[AdminOperationCreate] = []

    def create_operation(session: object, operation: AdminOperationCreate) -> AdminOperationRecord:
        created.append(operation)
        return operation_record(operation_type=operation.operation_type)

    service = AdminGraphService(
        cast(Session, object()),
        session_factory=cast(sessionmaker[Session], object()),
        neo4j_session=object(),
        background_tasks=background_tasks,
        create_operation_fn=create_operation,
        sync_rebuild_fn=lambda session, neo4j_session, triggered_by: ProjectionStats(
            persons_projected=12,
            encounters_projected=10,
            relationships_projected=10,
            started_at=NOW,
            finished_at=NOW,
        ),
    )

    response = service.start_sync_graph(AdminGraphSyncRequest(actor="local", mode="rebuild"))

    assert created[0].operation_type == "sync_graph_rebuild"
    assert response.preview == "figure-data sync-graph --rebuild"
    assert len(background_tasks.calls) == 1


def test_sync_graph_incremental_uses_incremental_operation_type() -> None:
    created: list[AdminOperationCreate] = []

    def create_operation(session: object, operation: AdminOperationCreate) -> AdminOperationRecord:
        created.append(operation)
        return operation_record(operation_type=operation.operation_type)

    service = AdminGraphService(
        cast(Session, object()),
        session_factory=cast(sessionmaker[Session], object()),
        neo4j_session=object(),
        background_tasks=FakeBackgroundTasks(),
        create_operation_fn=create_operation,
        sync_incremental_fn=lambda session, neo4j_session, triggered_by: IncrementalProjectionStats(
            persons_written=2,
            encounters_seen=3,
            relationships_written=1,
            relationships_deleted=2,
            started_at=NOW,
            finished_at=NOW,
        ),
    )

    response = service.start_sync_graph(AdminGraphSyncRequest(actor="local", mode="incremental"))

    assert created[0].operation_type == "sync_graph_incremental"
    assert response.preview == "figure-data sync-graph --incremental"


def test_validate_graph_requires_neo4j_session() -> None:
    service = AdminGraphService(
        cast(Session, object()),
        session_factory=cast(sessionmaker[Session], object()),
        neo4j_session=None,
        background_tasks=FakeBackgroundTasks(),
    )

    with pytest.raises(ApplicationError) as exc_info:
        service.start_validate_graph(AdminGraphOperationRequest(actor="local"))

    assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR
