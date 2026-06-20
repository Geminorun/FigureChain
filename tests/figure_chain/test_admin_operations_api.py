from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_admin_service
from figure_chain.schemas import AdminOperationDetailResponse, AdminOperationListResponse

OPERATION_ID = UUID("00000000-0000-0000-0000-000000000601")
OPERATOR_HEADERS = {"x-figure-actor": "lyl", "x-figure-role": "operator"}


class FakeAdminService:
    def list_operations(self, filters: object) -> AdminOperationListResponse:
        now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
        item = AdminOperationDetailResponse(
            operation_id=OPERATION_ID,
            operation_type="sync_graph_rebuild",
            actor="lyl",
            status="succeeded",
            request_payload={"mode": "rebuild"},
            result_summary={"relationships_written": 10},
            error_message=None,
            related_resource_type="graph_projection_batch",
            related_resource_id="batch-1",
            started_at=now,
            finished_at=now,
            created_at=now,
            updated_at=now,
        )
        return AdminOperationListResponse(items=[item], limit=50, offset=0, count=1)

    def get_operation(self, operation_id: UUID) -> AdminOperationDetailResponse:
        now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
        return AdminOperationDetailResponse(
            operation_id=operation_id,
            operation_type="sync_graph_rebuild",
            actor="lyl",
            status="succeeded",
            request_payload={"mode": "rebuild"},
            result_summary={"relationships_written": 10},
            error_message=None,
            related_resource_type="graph_projection_batch",
            related_resource_id="batch-1",
            started_at=now,
            finished_at=now,
            created_at=now,
            updated_at=now,
        )


def test_admin_operations_router_lists_operations() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_service] = lambda: FakeAdminService()
    try:
        response = TestClient(app).get(
            "/api/v1/admin/operations",
            params={"status": "succeeded", "operation_type": "sync_graph_rebuild"},
            headers=OPERATOR_HEADERS,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["operation_id"] == str(OPERATION_ID)


def test_admin_operations_router_gets_operation_detail() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_service] = lambda: FakeAdminService()
    try:
        response = TestClient(app).get(
            f"/api/v1/admin/operations/{OPERATION_ID}",
            headers=OPERATOR_HEADERS,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["operation_id"] == str(OPERATION_ID)


def test_admin_operations_router_requires_operator_role() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_service] = lambda: FakeAdminService()
    try:
        response = TestClient(app).get("/api/v1/admin/operations")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
