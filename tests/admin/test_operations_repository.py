from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from figure_data.admin.operations import (
    AdminOperationCreate,
    AdminOperationNotFoundError,
    AdminOperationUpdate,
    create_admin_operation,
    get_admin_operation,
    list_admin_operations,
    mark_admin_operation_finished,
    mark_admin_operation_running,
    sanitize_operation_payload,
)


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> MappingResult:
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class FakeSession:
    def __init__(self, *, found: bool = True) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []
        self.operation_id = UUID("00000000-0000-0000-0000-000000000601")
        self.now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
        self.found = found

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        sql = str(statement)
        current_params = params or {}
        self.statements.append(sql)
        self.params.append(current_params)
        if "insert into figure_data.admin_operations" in sql:
            return MappingResult(
                [
                    {
                        "id": self.operation_id,
                        "operation_type": current_params["operation_type"],
                        "actor": current_params["actor"],
                        "status": current_params["status"],
                        "request_payload": current_params["request_payload"],
                        "result_summary": current_params["result_summary"],
                        "error_message": current_params["error_message"],
                        "related_resource_type": current_params["related_resource_type"],
                        "related_resource_id": current_params["related_resource_id"],
                        "started_at": current_params["started_at"],
                        "finished_at": current_params["finished_at"],
                        "created_at": self.now,
                        "updated_at": self.now,
                    }
                ]
            )
        if "update figure_data.admin_operations" in sql:
            return MappingResult(
                [
                    {
                        "id": current_params["operation_id"],
                        "operation_type": "sync_graph_rebuild",
                        "actor": "lyl",
                        "status": current_params["status"],
                        "request_payload": {},
                        "result_summary": current_params.get("result_summary", {}),
                        "error_message": current_params.get("error_message"),
                        "related_resource_type": "graph_projection_batch",
                        "related_resource_id": "batch-1",
                        "started_at": current_params.get("started_at"),
                        "finished_at": current_params.get("finished_at"),
                        "created_at": self.now,
                        "updated_at": self.now,
                    }
                ]
            )
        if not self.found:
            return MappingResult([])
        return MappingResult(
            [
                {
                    "id": self.operation_id,
                    "operation_type": "sync_graph_rebuild",
                    "actor": "lyl",
                    "status": "succeeded",
                    "request_payload": {"mode": "rebuild"},
                    "result_summary": {"relationships_written": 10},
                    "error_message": None,
                    "related_resource_type": "graph_projection_batch",
                    "related_resource_id": "batch-1",
                    "started_at": self.now,
                    "finished_at": self.now,
                    "created_at": self.now,
                    "updated_at": self.now,
                }
            ]
        )


def test_create_admin_operation_sanitizes_payload_and_returns_record() -> None:
    session = FakeSession()

    record = create_admin_operation(
        session,  # type: ignore[arg-type]
        AdminOperationCreate(
            operation_type="sync_graph_rebuild",
            actor="lyl",
            status="queued",
            request_payload={"mode": "rebuild", "api_key": "secret"},
            related_resource_type="graph_projection_batch",
            related_resource_id="batch-1",
        ),
    )

    assert record.id == session.operation_id
    assert record.request_payload == {"mode": "rebuild", "api_key": "[redacted]"}
    assert session.params[0]["result_summary"] == {}
    assert "insert into figure_data.admin_operations" in session.statements[0]


def test_list_admin_operations_applies_filters() -> None:
    session = FakeSession()

    records = list_admin_operations(
        session,  # type: ignore[arg-type]
        status="succeeded",
        operation_type="sync_graph_rebuild",
        actor="lyl",
        limit=20,
        offset=5,
    )

    assert len(records) == 1
    assert "status = :status" in session.statements[0]
    assert "operation_type = :operation_type" in session.statements[0]
    assert "actor = :actor" in session.statements[0]
    assert session.params[0]["limit"] == 20
    assert session.params[0]["offset"] == 5


def test_get_admin_operation_raises_for_missing_record() -> None:
    session = FakeSession(found=False)

    with pytest.raises(AdminOperationNotFoundError):
        get_admin_operation(
            session,  # type: ignore[arg-type]
            UUID("00000000-0000-0000-0000-000000000999"),
        )


def test_mark_admin_operation_running_updates_status() -> None:
    session = FakeSession()
    operation_id = UUID("00000000-0000-0000-0000-000000000601")

    record = mark_admin_operation_running(session, operation_id)  # type: ignore[arg-type]

    assert record.status == "running"
    assert "update figure_data.admin_operations" in session.statements[0]
    assert session.params[0]["status"] == "running"


def test_mark_admin_operation_finished_updates_result_summary() -> None:
    session = FakeSession()
    operation_id = UUID("00000000-0000-0000-0000-000000000601")

    record = mark_admin_operation_finished(
        session,  # type: ignore[arg-type]
        operation_id,
        AdminOperationUpdate(
            status="succeeded",
            result_summary={"ok": True, "token": "secret"},
        ),
    )

    assert record.status == "succeeded"
    assert record.result_summary == {"ok": True, "token": "[redacted]"}


def test_sanitize_operation_payload_redacts_sensitive_keys() -> None:
    assert sanitize_operation_payload(
        {
            "REDIS_URL": "redis://localhost:6379/0",
            "nested": {"FIGURE_AI_API_KEY": "secret", "safe": "value"},
        }
    ) == {
        "REDIS_URL": "[redacted]",
        "nested": {"FIGURE_AI_API_KEY": "[redacted]", "safe": "value"},
    }
