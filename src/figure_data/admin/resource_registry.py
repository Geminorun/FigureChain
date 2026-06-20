from __future__ import annotations

from typing import cast

from figure_data.admin.resource_types import (
    ResourceColumnDefinition,
    ResourceDefinition,
    ResourceLink,
)


def _link(value: str | None) -> ResourceLink | None:
    return cast(ResourceLink | None, value)


def _text(name: str, *, default: bool = False, link: str | None = None) -> ResourceColumnDefinition:
    return ResourceColumnDefinition(
        name=name,
        label=name,
        type="string",
        default_selected=default,
        operators=("eq", "ne", "in", "ilike", "is_null", "is_not_null"),
        link=_link(link),
    )


def _int(name: str, *, default: bool = False, link: str | None = None) -> ResourceColumnDefinition:
    return ResourceColumnDefinition(
        name=name,
        label=name,
        type="integer",
        default_selected=default,
        operators=("eq", "ne", "in", "gte", "lte", "is_null", "is_not_null"),
        link=_link(link),
    )


def _uuid(name: str, *, default: bool = False, link: str | None = None) -> ResourceColumnDefinition:
    return ResourceColumnDefinition(
        name=name,
        label=name,
        type="uuid",
        default_selected=default,
        operators=("eq", "ne", "in", "is_null", "is_not_null"),
        link=_link(link),
    )


def _bool(name: str, *, default: bool = False) -> ResourceColumnDefinition:
    return ResourceColumnDefinition(
        name=name,
        label=name,
        type="boolean",
        default_selected=default,
        operators=("eq", "ne", "is_null", "is_not_null"),
    )


def _datetime(name: str, *, default: bool = False) -> ResourceColumnDefinition:
    return ResourceColumnDefinition(
        name=name,
        label=name,
        type="datetime",
        default_selected=default,
        operators=("eq", "ne", "gte", "lte", "is_null", "is_not_null"),
    )


RESOURCE_DEFINITIONS: tuple[ResourceDefinition, ...] = (
    ResourceDefinition(
        name="relationship_candidates",
        label="关系候选",
        table_sql="figure_data.relationship_candidates",
        primary_key="id",
        columns=(
            _int("id", default=True, link="candidate:relationship"),
            _uuid("person_a_id", default=True, link="person"),
            _uuid("person_b_id", default=True, link="person"),
            _text("association_label", default=True),
            _text("candidate_strength", default=True),
            _text("review_status", default=True),
            _uuid("promoted_encounter_id", default=True, link="encounter"),
        ),
        default_order_by="id",
        default_order_direction="desc",
    ),
    ResourceDefinition(
        name="kinship_candidates",
        label="亲属候选",
        table_sql="figure_data.kinship_candidates",
        primary_key="id",
        columns=(
            _int("id", default=True, link="candidate:kinship"),
            _uuid("person_a_id", default=True, link="person"),
            _uuid("person_b_id", default=True, link="person"),
            _text("kinship_label_zh", default=True),
            _text("candidate_strength", default=True),
            _text("review_status", default=True),
            _uuid("promoted_encounter_id", default=True, link="encounter"),
        ),
        default_order_by="id",
        default_order_direction="desc",
    ),
    ResourceDefinition(
        name="encounters",
        label="Encounter",
        table_sql="figure_data.encounters",
        primary_key="id",
        columns=(
            _uuid("id", default=True, link="encounter"),
            _uuid("person_a_id", default=True, link="person"),
            _uuid("person_b_id", default=True, link="person"),
            _text("encounter_kind", default=True),
            _text("certainty_level", default=True),
            _bool("path_eligible", default=True),
            _text("status", default=True),
            _datetime("reviewed_at", default=True),
        ),
        default_order_by="reviewed_at",
        default_order_direction="desc",
    ),
    ResourceDefinition(
        name="encounter_evidence",
        label="Encounter 证据",
        table_sql="figure_data.encounter_evidence",
        primary_key="id",
        columns=(
            _int("id", default=True),
            _uuid("encounter_id", default=True, link="encounter"),
            _text("candidate_table", default=True),
            _int("candidate_id", default=True),
            _int("source_ref_id", default=True, link="source_ref"),
            _int("source_work_id", default=True, link="source_work"),
            _text("evidence_kind", default=True),
        ),
        default_order_by="id",
        default_order_direction="desc",
    ),
    ResourceDefinition(
        name="persons",
        label="人物",
        table_sql="figure_data.persons",
        primary_key="id",
        columns=(
            _uuid("id", default=True, link="person"),
            _text("primary_name_zh_hant", default=True),
            _text("primary_name_zh_hans", default=True),
            _text("primary_name_romanized", default=True),
            _int("birth_year", default=True),
            _int("death_year", default=True),
            _int("dynasty_code", default=True),
        ),
        default_order_by="id",
        default_order_direction="asc",
    ),
    ResourceDefinition(
        name="source_refs",
        label="来源引用",
        table_sql="figure_data.source_refs",
        primary_key="id",
        columns=(
            _int("id", default=True, link="source_ref"),
            _int("source_work_id", default=True, link="source_work"),
            _text("ref_source_table", default=True),
            _text("ref_source_pk", default=True),
            _text("pages", default=True),
        ),
        default_order_by="id",
        default_order_direction="desc",
    ),
    ResourceDefinition(
        name="source_works",
        label="来源书目",
        table_sql="figure_data.source_works",
        primary_key="id",
        columns=(
            _int("id", default=True, link="source_work"),
            _int("text_code", default=True),
            _text("title_zh", default=True),
            _text("title_en", default=True),
        ),
        default_order_by="id",
        default_order_direction="desc",
    ),
    ResourceDefinition(
        name="ai_generation_jobs",
        label="AI 任务",
        table_sql="figure_data.ai_generation_jobs",
        primary_key="id",
        columns=(
            _uuid("id", default=True, link="ai_job"),
            _text("job_type", default=True),
            _text("target_kind", default=True),
            _int("target_id", default=True),
            _text("status", default=True),
            _text("queue_backend", default=True),
            _int("attempt_count", default=True),
            _datetime("created_at", default=True),
        ),
        default_order_by="created_at",
        default_order_direction="desc",
    ),
    ResourceDefinition(
        name="ai_job_events",
        label="AI 任务事件",
        table_sql="figure_data.ai_job_events",
        primary_key="id",
        columns=(
            _uuid("id", default=True, link="ai_job_event"),
            _uuid("job_id", default=True, link="ai_job"),
            _text("event_type", default=True),
            _text("actor", default=True),
            _text("message", default=True),
            _datetime("created_at", default=True),
        ),
        default_order_by="created_at",
        default_order_direction="desc",
    ),
    ResourceDefinition(
        name="graph_projection_batches",
        label="图投影批次",
        table_sql="figure_data.graph_projection_batches",
        primary_key="id",
        columns=(
            _uuid("id", default=True, link="graph_projection_batch"),
            _text("mode", default=True),
            _text("status", default=True),
            _text("triggered_by", default=True),
            _text("validation_status", default=True),
            _datetime("started_at", default=True),
            _datetime("finished_at", default=True),
        ),
        default_order_by="started_at",
        default_order_direction="desc",
    ),
    ResourceDefinition(
        name="admin_operations",
        label="后台操作历史",
        table_sql="figure_data.admin_operations",
        primary_key="id",
        columns=(
            _uuid("id", default=True, link="admin_operation"),
            _text("operation_type", default=True),
            _text("actor", default=True),
            _text("status", default=True),
            _text("related_resource_type", default=True),
            _text("related_resource_id", default=True),
            _datetime("created_at", default=True),
        ),
        default_order_by="created_at",
        default_order_direction="desc",
    ),
)

_RESOURCE_BY_NAME = {resource.name: resource for resource in RESOURCE_DEFINITIONS}


def list_resource_definitions() -> tuple[ResourceDefinition, ...]:
    return RESOURCE_DEFINITIONS


def get_resource_definition(name: str) -> ResourceDefinition:
    try:
        return _RESOURCE_BY_NAME[name]
    except KeyError as exc:
        raise KeyError(f"unknown admin resource: {name}") from exc
