from __future__ import annotations

from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_admin_resources_service
from figure_chain.schemas import (
    AdminResourceColumnResponse,
    AdminResourceListResponse,
    AdminResourceQueryResponse,
    AdminResourceResponse,
)

OPERATOR_HEADERS = {"x-figure-role": "operator", "x-figure-actor": "local"}


class FakeAdminResourcesService:
    def list_resources(self) -> AdminResourceListResponse:
        return AdminResourceListResponse(
            resources=[
                AdminResourceResponse(
                    name="persons",
                    label="人物",
                    primary_key="id",
                    default_order_by="id",
                    default_order_direction="asc",
                    columns=[
                        AdminResourceColumnResponse(
                            key="id",
                            label="id",
                            type="uuid",
                            operators=["eq"],
                            selectable=True,
                            filterable=True,
                            sortable=True,
                            default_selected=True,
                            link="person",
                        )
                    ],
                )
            ]
        )

    def query_resource(self, request: object) -> AdminResourceQueryResponse:
        return AdminResourceQueryResponse(
            resource="persons",
            columns=[
                AdminResourceColumnResponse(
                    key="id",
                    label="id",
                    type="uuid",
                    operators=["eq"],
                    selectable=True,
                    filterable=True,
                    sortable=True,
                    default_selected=True,
                    link="person",
                )
            ],
            rows=[{"id": "person-1"}],
            limit=50,
            offset=0,
            preview="resource=persons select=id where=none order_by=id asc limit=50 offset=0",
        )


def test_admin_resources_api_requires_operator_role() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_resources_service] = lambda: FakeAdminResourcesService()
    try:
        response = TestClient(app).get(
            "/api/v1/admin/resources",
            headers={"x-figure-role": "explorer"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_admin_resources_api_lists_resources() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_resources_service] = lambda: FakeAdminResourcesService()
    try:
        response = TestClient(app).get(
            "/api/v1/admin/resources",
            headers=OPERATOR_HEADERS,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["resources"][0]["name"] == "persons"


def test_admin_resources_api_queries_resource() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_resources_service] = lambda: FakeAdminResourcesService()
    try:
        response = TestClient(app).post(
            "/api/v1/admin/resources/query",
            headers=OPERATOR_HEADERS,
            json={
                "resource": "persons",
                "select": ["id"],
                "filters": [],
                "order_by": "id",
                "order_direction": "asc",
                "limit": 50,
                "offset": 0,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["resource"] == "persons"
    assert body["rows"] == [{"id": "person-1"}]
