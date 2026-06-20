from __future__ import annotations

from collections.abc import Callable
from typing import cast

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    AdminResourceColumnResponse,
    AdminResourceListResponse,
    AdminResourceQueryRequest,
    AdminResourceQueryResponse,
    AdminResourceResponse,
)
from figure_data.admin.resource_query import (
    ResourceFilter,
    ResourceQuery,
    ResourceQueryResult,
    execute_resource_query,
)
from figure_data.admin.resource_registry import (
    get_resource_definition,
    list_resource_definitions,
)
from figure_data.admin.resource_types import (
    ResourceColumnDefinition,
    ResourceDefinition,
    ResourceOperator,
)

ExecuteResourceQueryFn = Callable[[Session, ResourceQuery], ResourceQueryResult]


class AdminResourcesService:
    def __init__(
        self,
        session: Session,
        *,
        execute_query_fn: ExecuteResourceQueryFn = execute_resource_query,
    ) -> None:
        self._session = session
        self._execute_query_fn = execute_query_fn

    def list_resources(self) -> AdminResourceListResponse:
        return AdminResourceListResponse(
            resources=[
                self._resource_definition(resource)
                for resource in list_resource_definitions()
            ]
        )

    def query_resource(self, request: AdminResourceQueryRequest) -> AdminResourceQueryResponse:
        try:
            definition = get_resource_definition(request.resource)
            query = ResourceQuery(
                resource=request.resource,
                select=tuple(request.select),
                filters=tuple(
                    ResourceFilter(
                        field=resource_filter.field,
                        operator=cast(ResourceOperator, resource_filter.operator),
                        value=resource_filter.value,
                    )
                    for resource_filter in request.filters
                ),
                order_by=request.order_by or definition.default_order_by,
                order_direction=request.order_direction,
                limit=request.limit,
                offset=request.offset,
            )
            result = self._execute_query_fn(self._session, query)
        except (KeyError, ValueError) as exc:
            raise ApplicationError(
                code=ErrorCode.INVALID_REQUEST,
                message="invalid admin resource query",
                details={"reason": str(exc)},
            ) from exc

        return AdminResourceQueryResponse(
            resource=result.resource,
            columns=[self._column_result(column) for column in result.columns],
            rows=result.rows,
            limit=result.limit,
            offset=result.offset,
            preview=result.preview,
        )

    def _resource_definition(self, resource: ResourceDefinition) -> AdminResourceResponse:
        return AdminResourceResponse(
            name=resource.name,
            label=resource.label,
            primary_key=resource.primary_key,
            default_order_by=resource.default_order_by,
            default_order_direction=resource.default_order_direction,
            columns=[self._column_definition(column) for column in resource.columns],
        )

    def _column_definition(
        self,
        column: ResourceColumnDefinition,
    ) -> AdminResourceColumnResponse:
        return AdminResourceColumnResponse(
            key=column.name,
            label=column.label,
            type=column.type,
            operators=list(column.operators),
            selectable=column.selectable,
            filterable=column.filterable,
            sortable=column.sortable,
            default_selected=column.default_selected,
            link=column.link,
        )

    def _column_result(self, column: dict[str, object]) -> AdminResourceColumnResponse:
        operators = cast(list[object], column["operators"])
        return AdminResourceColumnResponse(
            key=str(column["key"]),
            label=str(column["label"]),
            type=str(column["type"]),
            operators=[str(operator) for operator in operators],
            selectable=bool(column["selectable"]),
            filterable=bool(column["filterable"]),
            sortable=bool(column["sortable"]),
            default_selected=bool(column["default_selected"]),
            link=None if column["link"] is None else str(column["link"]),
        )
