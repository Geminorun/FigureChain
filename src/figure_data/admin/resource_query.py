from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.admin.resource_preview import build_resource_query_preview
from figure_data.admin.resource_registry import get_resource_definition
from figure_data.admin.resource_types import (
    ResourceColumnDefinition,
    ResourceOperator,
)


class ResourceQuerySession(Protocol):
    def execute(self, statement: object, params: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class ResourceFilter:
    field: str
    operator: ResourceOperator
    value: object | None


@dataclass(frozen=True)
class ResourceQuery:
    resource: str
    select: tuple[str, ...]
    filters: tuple[ResourceFilter, ...]
    order_by: str
    order_direction: Literal["asc", "desc"]
    limit: int
    offset: int


@dataclass(frozen=True)
class ResourceQueryResult:
    resource: str
    columns: list[dict[str, object]]
    rows: list[dict[str, object]]
    limit: int
    offset: int
    preview: str


def execute_resource_query(
    session: Session | ResourceQuerySession,
    query: ResourceQuery,
) -> ResourceQueryResult:
    definition = get_resource_definition(query.resource)
    columns_by_name = {column.name: column for column in definition.columns}
    selected_columns = _resolve_selected_columns(query.select, columns_by_name)
    filter_sql, params = _compile_filters(query.filters, columns_by_name)
    order_by = _resolve_sort_column(query.order_by, columns_by_name)
    limit = min(max(query.limit, 1), 200)
    offset = max(query.offset, 0)
    params.update({"limit": limit, "offset": offset})

    where_clause = f" where {' and '.join(filter_sql)}" if filter_sql else ""
    statement = text(
        f"select {', '.join(selected_columns)} "
        f"from {definition.table_sql}"
        f"{where_clause} "
        f"order by {order_by} {query.order_direction} "
        "limit :limit offset :offset"
    )
    rows = [dict(row) for row in session.execute(statement, params).mappings().all()]

    return ResourceQueryResult(
        resource=query.resource,
        columns=[
            _column_to_response(columns_by_name[column_name])
            for column_name in selected_columns
        ],
        rows=rows,
        limit=limit,
        offset=offset,
        preview=build_resource_query_preview(
            ResourceQuery(
                resource=query.resource,
                select=tuple(selected_columns),
                filters=query.filters,
                order_by=order_by,
                order_direction=query.order_direction,
                limit=limit,
                offset=offset,
            )
        ),
    )


def _resolve_selected_columns(
    select: tuple[str, ...],
    columns_by_name: dict[str, ResourceColumnDefinition],
) -> list[str]:
    selected = list(select)
    if not selected:
        selected = [
            column.name
            for column in columns_by_name.values()
            if column.default_selected and column.selectable
        ]
    for field in selected:
        column = _require_column(field, columns_by_name)
        if not column.selectable:
            raise ValueError(f"field is not selectable: {field}")
    return selected


def _compile_filters(
    filters: tuple[ResourceFilter, ...],
    columns_by_name: dict[str, ResourceColumnDefinition],
) -> tuple[list[str], dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for index, resource_filter in enumerate(filters):
        column = _require_column(resource_filter.field, columns_by_name)
        if not column.filterable:
            raise ValueError(f"field is not filterable: {resource_filter.field}")
        if resource_filter.operator not in column.operators:
            raise ValueError(
                f"operator {resource_filter.operator} is not allowed for {resource_filter.field}"
            )
        param_name = f"filter_{index}"
        clause = _compile_filter_clause(resource_filter, param_name)
        clauses.append(clause)
        if resource_filter.operator not in ("is_null", "is_not_null"):
            params[param_name] = _coerce_filter_value(resource_filter)
    return clauses, params


def _compile_filter_clause(resource_filter: ResourceFilter, param_name: str) -> str:
    field = resource_filter.field
    operator = resource_filter.operator
    if operator == "eq":
        return f"{field} = :{param_name}"
    if operator == "ne":
        return f"{field} <> :{param_name}"
    if operator == "in":
        return f"{field} = any(:{param_name})"
    if operator == "ilike":
        return f"{field} ilike :{param_name}"
    if operator == "gte":
        return f"{field} >= :{param_name}"
    if operator == "lte":
        return f"{field} <= :{param_name}"
    if operator == "is_null":
        return f"{field} is null"
    if operator == "is_not_null":
        return f"{field} is not null"
    raise ValueError(f"unsupported operator: {operator}")


def _coerce_filter_value(resource_filter: ResourceFilter) -> Any:
    if resource_filter.operator == "ilike":
        return f"%{resource_filter.value}%"
    if resource_filter.operator == "in":
        value = resource_filter.value
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]
    return resource_filter.value


def _resolve_sort_column(
    order_by: str,
    columns_by_name: dict[str, ResourceColumnDefinition],
) -> str:
    column = _require_column(order_by, columns_by_name)
    if not column.sortable:
        raise ValueError(f"field is not sortable: {order_by}")
    return column.name


def _require_column(
    field: str,
    columns_by_name: dict[str, ResourceColumnDefinition],
) -> ResourceColumnDefinition:
    try:
        return columns_by_name[field]
    except KeyError as exc:
        raise ValueError(f"unknown admin resource field: {field}") from exc


def _column_to_response(column: ResourceColumnDefinition) -> dict[str, object]:
    return {
        "key": column.name,
        "label": column.label,
        "type": column.type,
        "operators": list(column.operators),
        "selectable": column.selectable,
        "filterable": column.filterable,
        "sortable": column.sortable,
        "default_selected": column.default_selected,
        "link": column.link,
    }
