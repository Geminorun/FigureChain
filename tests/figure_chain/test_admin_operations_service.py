from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.services.admin import AdminOperationFilters, AdminService
from figure_data.admin.operations import AdminOperationNotFoundError, AdminOperationRecord

OPERATION_ID = UUID("00000000-0000-0000-0000-000000000601")
NOW = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)


def operation_record() -> AdminOperationRecord:
    return AdminOperationRecord(
        id=OPERATION_ID,
        operation_type="sync_graph_rebuild",
        actor="lyl",
        status="succeeded",
        request_payload={"mode": "rebuild"},
        result_summary={"relationships_written": 10},
        error_message=None,
        related_resource_type="graph_projection_batch",
        related_resource_id="batch-1",
        started_at=NOW,
        finished_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def test_admin_service_lists_operations() -> None:
    calls: list[AdminOperationFilters] = []

    def list_operations(session: object, **kwargs: object) -> list[AdminOperationRecord]:
        calls.append(AdminOperationFilters(**kwargs))  # type: ignore[arg-type]
        return [operation_record()]

    service = AdminService(cast(Session, object()), list_operations_fn=list_operations)

    response = service.list_operations(
        AdminOperationFilters(
            status="succeeded",
            operation_type="sync_graph_rebuild",
            actor="lyl",
            limit=20,
            offset=5,
        )
    )

    assert response.count == 1
    assert response.items[0].operation_id == OPERATION_ID
    assert response.items[0].result_summary == {"relationships_written": 10}
    assert calls[0].limit == 20
    assert calls[0].offset == 5


def test_admin_service_gets_operation() -> None:
    service = AdminService(
        cast(Session, object()),
        get_operation_fn=lambda session, operation_id: operation_record(),
    )

    response = service.get_operation(OPERATION_ID)

    assert response.operation_id == OPERATION_ID
    assert response.operation_type == "sync_graph_rebuild"
    assert response.related_resource_type == "graph_projection_batch"


def test_admin_service_maps_missing_operation_to_application_error() -> None:
    def missing(session: object, operation_id: UUID) -> AdminOperationRecord:
        raise AdminOperationNotFoundError("missing")

    service = AdminService(cast(Session, object()), get_operation_fn=missing)

    with pytest.raises(ApplicationError) as exc_info:
        service.get_operation(OPERATION_ID)

    assert exc_info.value.code == ErrorCode.ADMIN_OPERATION_NOT_FOUND
