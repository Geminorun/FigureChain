from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import AdminResourceQueryRequest
from figure_chain.services.admin_resources import AdminResourcesService
from figure_data.admin.resource_query import ResourceQuery, ResourceQueryResult


def test_admin_resources_service_lists_metadata() -> None:
    service = AdminResourcesService(cast(Session, object()))

    response = service.list_resources()

    resource_names = {resource.name for resource in response.resources}
    assert "relationship_candidates" in resource_names
    assert "persons" in resource_names
    persons = next(resource for resource in response.resources if resource.name == "persons")
    assert persons.primary_key == "id"
    assert any(column.key == "primary_name_zh_hant" for column in persons.columns)


def test_admin_resources_service_executes_query() -> None:
    calls: list[ResourceQuery] = []

    def execute_query(session: object, query: ResourceQuery) -> ResourceQueryResult:
        calls.append(query)
        return ResourceQueryResult(
            resource=query.resource,
            columns=[
                {
                    "key": "id",
                    "label": "id",
                    "type": "uuid",
                    "operators": ["eq"],
                    "selectable": True,
                    "filterable": True,
                    "sortable": True,
                    "default_selected": True,
                    "link": "person",
                }
            ],
            rows=[{"id": "person-1"}],
            limit=query.limit,
            offset=query.offset,
            preview="resource=persons select=id where=none order_by=id asc limit=20 offset=0",
        )

    service = AdminResourcesService(cast(Session, object()), execute_query_fn=execute_query)

    response = service.query_resource(
        AdminResourceQueryRequest(
            resource="persons",
            select=["id"],
            filters=[],
            order_by="id",
            order_direction="asc",
            limit=20,
            offset=0,
        )
    )

    assert response.resource == "persons"
    assert response.rows == [{"id": "person-1"}]
    assert calls[0].select == ("id",)
    assert calls[0].order_by == "id"


def test_admin_resources_service_maps_invalid_query() -> None:
    def execute_query(session: object, query: ResourceQuery) -> ResourceQueryResult:
        raise ValueError("password_hash")

    service = AdminResourcesService(cast(Session, object()), execute_query_fn=execute_query)

    with pytest.raises(ApplicationError) as exc_info:
        service.query_resource(
            AdminResourceQueryRequest(
                resource="persons",
                select=["password_hash"],
                filters=[],
                order_by="id",
                order_direction="asc",
                limit=20,
                offset=0,
            )
        )

    assert exc_info.value.code == ErrorCode.INVALID_REQUEST
    assert exc_info.value.details["reason"] == "password_hash"
