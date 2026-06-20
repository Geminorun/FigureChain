from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from figure_data.admin.resource_query import ResourceFilter, ResourceQuery


def build_resource_query_preview(query: ResourceQuery) -> str:
    candidate_kind = _candidate_kind_for_resource(query.resource)
    review_status = _find_review_status_filter(query.filters)
    if candidate_kind and review_status is not None:
        return (
            f"figure-data review-candidates --kind {candidate_kind} "
            f"--status {review_status} --limit {query.limit}"
        )

    where = " and ".join(
        f"{resource_filter.field} {resource_filter.operator} {resource_filter.value}"
        for resource_filter in query.filters
    )
    where_preview = where if where else "none"
    return (
        f"resource={query.resource} select={','.join(query.select)} "
        f"where={where_preview} order_by={query.order_by} {query.order_direction} "
        f"limit={query.limit} offset={query.offset}"
    )


def _candidate_kind_for_resource(resource: str) -> str | None:
    if resource == "relationship_candidates":
        return "relationship"
    if resource == "kinship_candidates":
        return "kinship"
    return None


def _find_review_status_filter(filters: tuple[ResourceFilter, ...]) -> object | None:
    for resource_filter in filters:
        if resource_filter.field == "review_status" and resource_filter.operator == "eq":
            return resource_filter.value
    return None
