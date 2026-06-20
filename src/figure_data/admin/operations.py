from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "authorization",
    "redis_url",
)


class AdminOperationNotFoundError(ValueError):
    """Raised when an admin operation cannot be found."""


@dataclass(frozen=True)
class AdminOperationCreate:
    operation_type: str
    actor: str
    status: str = "queued"
    request_payload: dict[str, Any] = field(default_factory=dict)
    result_summary: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    related_resource_type: str | None = None
    related_resource_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class AdminOperationUpdate:
    status: str
    result_summary: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class AdminOperationRecord:
    id: UUID
    operation_type: str
    actor: str
    status: str
    request_payload: dict[str, Any]
    result_summary: dict[str, Any]
    error_message: str | None
    related_resource_type: str | None
    related_resource_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


def create_admin_operation(
    session: Session,
    operation: AdminOperationCreate,
) -> AdminOperationRecord:
    now = datetime.now(UTC)
    row = (
        session.execute(
            text(
                """
                insert into figure_data.admin_operations (
                  id, operation_type, actor, status, request_payload, result_summary,
                  error_message, related_resource_type, related_resource_id,
                  started_at, finished_at, created_at, updated_at
                ) values (
                  gen_random_uuid(), :operation_type, :actor, :status,
                  :request_payload, :result_summary,
                  :error_message, :related_resource_type, :related_resource_id,
                  :started_at, :finished_at, :created_at, :updated_at
                )
                returning
                  id, operation_type, actor, status, request_payload, result_summary,
                  error_message, related_resource_type, related_resource_id,
                  started_at, finished_at, created_at, updated_at
                """
            ).bindparams(
                bindparam("request_payload", type_=JSONB),
                bindparam("result_summary", type_=JSONB),
            ),
            {
                "operation_type": operation.operation_type,
                "actor": operation.actor,
                "status": operation.status,
                "request_payload": sanitize_operation_payload(operation.request_payload),
                "result_summary": sanitize_operation_payload(operation.result_summary),
                "error_message": operation.error_message,
                "related_resource_type": operation.related_resource_type,
                "related_resource_id": operation.related_resource_id,
                "started_at": operation.started_at,
                "finished_at": operation.finished_at,
                "created_at": now,
                "updated_at": now,
            },
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise RuntimeError("failed to create admin operation")
    return _record(cast(Mapping[str, Any], row))


def list_admin_operations(
    session: Session,
    *,
    status: str | None = None,
    operation_type: str | None = None,
    actor: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminOperationRecord]:
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        clauses.append("status = :status")
        params["status"] = status
    if operation_type:
        clauses.append("operation_type = :operation_type")
        params["operation_type"] = operation_type
    if actor:
        clauses.append("actor = :actor")
        params["actor"] = actor
    where_sql = f"where {' and '.join(clauses)}" if clauses else ""
    rows = (
        session.execute(
            text(
                f"""
                select
                  id, operation_type, actor, status, request_payload, result_summary,
                  error_message, related_resource_type, related_resource_id,
                  started_at, finished_at, created_at, updated_at
                from figure_data.admin_operations
                {where_sql}
                order by created_at desc
                limit :limit offset :offset
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [_record(cast(Mapping[str, Any], row)) for row in rows]


def get_admin_operation(session: Session, operation_id: UUID) -> AdminOperationRecord:
    row = (
        session.execute(
            text(
                """
                select
                  id, operation_type, actor, status, request_payload, result_summary,
                  error_message, related_resource_type, related_resource_id,
                  started_at, finished_at, created_at, updated_at
                from figure_data.admin_operations
                where id = :operation_id
                """
            ),
            {"operation_id": operation_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AdminOperationNotFoundError(f"admin operation not found: {operation_id}")
    return _record(cast(Mapping[str, Any], row))


def mark_admin_operation_running(
    session: Session,
    operation_id: UUID,
) -> AdminOperationRecord:
    now = datetime.now(UTC)
    return _update_operation(
        session,
        operation_id,
        status="running",
        result_summary={},
        error_message=None,
        started_at=now,
        finished_at=None,
        updated_at=now,
    )


def mark_admin_operation_finished(
    session: Session,
    operation_id: UUID,
    update: AdminOperationUpdate,
) -> AdminOperationRecord:
    now = datetime.now(UTC)
    return _update_operation(
        session,
        operation_id,
        status=update.status,
        result_summary=update.result_summary,
        error_message=update.error_message,
        started_at=None,
        finished_at=update.finished_at or now,
        updated_at=now,
    )


def sanitize_operation_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                sanitized[key_text] = "[redacted]"
            else:
                sanitized[key_text] = sanitize_operation_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_operation_payload(item) for item in value]
    return value


def _update_operation(
    session: Session,
    operation_id: UUID,
    *,
    status: str,
    result_summary: dict[str, Any],
    error_message: str | None,
    started_at: datetime | None,
    finished_at: datetime | None,
    updated_at: datetime,
) -> AdminOperationRecord:
    set_started_at = ", started_at = coalesce(started_at, :started_at)" if started_at else ""
    row = (
        session.execute(
            text(
                f"""
                update figure_data.admin_operations
                   set status = :status,
                       result_summary = :result_summary,
                       error_message = :error_message,
                       finished_at = :finished_at,
                       updated_at = :updated_at
                       {set_started_at}
                 where id = :operation_id
             returning
                  id, operation_type, actor, status, request_payload, result_summary,
                  error_message, related_resource_type, related_resource_id,
                  started_at, finished_at, created_at, updated_at
                """
            ).bindparams(bindparam("result_summary", type_=JSONB)),
            {
                "operation_id": operation_id,
                "status": status,
                "result_summary": sanitize_operation_payload(result_summary),
                "error_message": error_message,
                "started_at": started_at,
                "finished_at": finished_at,
                "updated_at": updated_at,
            },
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AdminOperationNotFoundError(f"admin operation not found: {operation_id}")
    return _record(cast(Mapping[str, Any], row))


def _record(row: Mapping[str, Any]) -> AdminOperationRecord:
    return AdminOperationRecord(
        id=_uuid(row["id"]),
        operation_type=str(row["operation_type"]),
        actor=str(row["actor"]),
        status=str(row["status"]),
        request_payload=_loaded_dict(row["request_payload"]),
        result_summary=_loaded_dict(row["result_summary"]),
        error_message=None if row["error_message"] is None else str(row["error_message"]),
        related_resource_type=(
            None if row["related_resource_type"] is None else str(row["related_resource_type"])
        ),
        related_resource_id=(
            None if row["related_resource_id"] is None else str(row["related_resource_id"])
        ),
        started_at=_optional_datetime(row["started_at"]),
        finished_at=_optional_datetime(row["finished_at"]),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
    )


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _optional_datetime(value: object) -> datetime | None:
    return None if value is None else _datetime(value)


def _loaded_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
