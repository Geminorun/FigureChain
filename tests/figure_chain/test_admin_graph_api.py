from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from httpx import Response

from figure_chain.app import create_app
from figure_chain.dependencies import get_admin_graph_service
from figure_chain.schemas import (
    AdminGraphOperationResponse,
    AdminGraphStatusResponse,
    AdminGraphSyncRequest,
)

OPERATION_ID = UUID("00000000-0000-0000-0000-000000000701")
OPERATOR_HEADERS = {"x-figure-role": "operator", "x-figure-actor": "local"}


class FakeAdminGraphService:
    def get_status(self) -> AdminGraphStatusResponse:
        return AdminGraphStatusResponse(
            latest_success=None,
            latest_failed=None,
            active_encounter_count=10,
            path_eligible_encounter_count=8,
            stale_running_operations=[],
        )

    def start_validate_encounters(self, request: object) -> AdminGraphOperationResponse:
        return _operation("validate_encounters", "figure-data validate-encounters")

    def start_sync_graph(self, request: AdminGraphSyncRequest) -> AdminGraphOperationResponse:
        mode = request.mode
        operation_type = f"sync_graph_{mode}"
        preview = f"figure-data sync-graph --{mode}"
        return _operation(operation_type, preview)

    def start_validate_graph(self, request: object) -> AdminGraphOperationResponse:
        return _operation("validate_graph", "figure-data validate-graph")


def _operation(operation_type: str, preview: str) -> AdminGraphOperationResponse:
    return AdminGraphOperationResponse(
        operation_id=OPERATION_ID,
        operation_type=operation_type,
        status="queued",
        preview=preview,
    )


def test_admin_graph_status_requires_operator_role() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_graph_service] = lambda: FakeAdminGraphService()
    try:
        response = TestClient(app).get(
            "/api/v1/admin/graph/status",
            headers={"x-figure-role": "explorer"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_admin_graph_status_returns_counts() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_graph_service] = lambda: FakeAdminGraphService()
    try:
        response = TestClient(app).get(
            "/api/v1/admin/graph/status",
            headers=OPERATOR_HEADERS,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["active_encounter_count"] == 10


def test_admin_graph_validate_encounters_returns_operation_id() -> None:
    response = _post_graph_action(
        "/api/v1/admin/graph/validate-encounters",
        {"actor": "local"},
    )

    assert response.status_code == 200
    assert response.json()["operation_id"] == str(OPERATION_ID)
    assert response.json()["operation_type"] == "validate_encounters"


def test_admin_graph_sync_accepts_rebuild() -> None:
    response = _post_graph_action(
        "/api/v1/admin/graph/sync",
        {"mode": "rebuild", "actor": "local"},
    )

    assert response.status_code == 200
    assert response.json()["operation_type"] == "sync_graph_rebuild"


def test_admin_graph_sync_accepts_incremental() -> None:
    response = _post_graph_action(
        "/api/v1/admin/graph/sync",
        {"mode": "incremental", "actor": "local"},
    )

    assert response.status_code == 200
    assert response.json()["operation_type"] == "sync_graph_incremental"


def test_admin_graph_validate_graph_returns_operation_id() -> None:
    response = _post_graph_action(
        "/api/v1/admin/graph/validate-graph",
        {"actor": "local"},
    )

    assert response.status_code == 200
    assert response.json()["operation_id"] == str(OPERATION_ID)
    assert response.json()["preview"] == "figure-data validate-graph"


def _post_graph_action(path: str, body: dict[str, object]) -> Response:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_graph_service] = lambda: FakeAdminGraphService()
    try:
        return TestClient(app).post(path, headers=OPERATOR_HEADERS, json=body)
    finally:
        app.dependency_overrides.clear()
