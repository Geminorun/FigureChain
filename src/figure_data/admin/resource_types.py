from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ResourceColumnType = Literal["string", "integer", "number", "boolean", "datetime", "uuid", "json"]
ResourceOperator = Literal["eq", "ne", "in", "ilike", "gte", "lte", "is_null", "is_not_null"]
ResourceLink = Literal[
    "person",
    "candidate:relationship",
    "candidate:kinship",
    "encounter",
    "source_ref",
    "source_work",
    "ai_job",
    "ai_job_event",
    "graph_projection_batch",
    "admin_operation",
]


@dataclass(frozen=True)
class ResourceColumnDefinition:
    name: str
    label: str
    type: ResourceColumnType
    selectable: bool = True
    filterable: bool = True
    sortable: bool = True
    default_selected: bool = False
    operators: tuple[ResourceOperator, ...] = ("eq", "ne")
    link: ResourceLink | None = None


@dataclass(frozen=True)
class ResourceDefinition:
    name: str
    label: str
    table_sql: str
    primary_key: str
    columns: tuple[ResourceColumnDefinition, ...]
    default_order_by: str
    default_order_direction: Literal["asc", "desc"]
