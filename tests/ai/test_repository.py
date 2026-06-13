from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from figure_data.ai.repository import (
    create_ai_run,
    get_ai_run,
    mark_ai_run_failed,
    mark_ai_run_succeeded,
)
from figure_data.ai.types import NewAIRun


@dataclass
class ScalarResult:
    value: object

    def scalar_one(self) -> object:
        return self.value


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> "MappingResult":
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []
        self.run_id = UUID("00000000-0000-0000-0000-000000000001")

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> object:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params)
        if "returning id" in sql:
            return ScalarResult(self.run_id)
        if "from figure_data.ai_runs" in sql:
            return MappingResult(
                [
                    {
                        "run_id": self.run_id,
                        "purpose": "ai_foundation_diagnostic",
                        "provider": "fake",
                        "model_name": "fake-model",
                        "prompt_version_id": UUID("00000000-0000-0000-0000-000000000002"),
                        "prompt_key": "ai_foundation_diagnostic",
                        "prompt_version": "2026-06-13.1",
                        "input_hash": "hash",
                        "input_snapshot": {"echo_id": "abc"},
                        "output_snapshot": {
                            "message": "ready",
                            "echo_id": "abc",
                            "warnings": [],
                        },
                        "raw_output_excerpt": '{"message":"ready"}',
                        "status": "succeeded",
                        "schema_valid": True,
                        "error_code": None,
                        "error_message": None,
                        "started_at": datetime.now(UTC),
                        "finished_at": datetime.now(UTC),
                        "created_by": "test",
                    }
                ]
            )
        return ScalarResult(None)


def test_create_ai_run_inserts_running_record() -> None:
    session = FakeSession()

    run_id = create_ai_run(
        session,  # type: ignore[arg-type]
        NewAIRun(
            purpose="ai_foundation_diagnostic",
            provider="fake",
            model_name="fake-model",
            prompt_version_id=UUID("00000000-0000-0000-0000-000000000002"),
            input_hash="hash",
            input_snapshot={"echo_id": "abc"},
            created_by="test",
        ),
    )

    assert run_id == session.run_id
    assert "insert into figure_data.ai_runs" in session.statements[0]
    params = session.params[0]
    assert params is not None
    assert params["status"] == "running"
    assert params["schema_valid"] is False


def test_mark_ai_run_succeeded_updates_output_snapshot() -> None:
    session = FakeSession()

    mark_ai_run_succeeded(
        session,  # type: ignore[arg-type]
        run_id=session.run_id,
        output_snapshot={"message": "ready"},
        raw_output='{"message":"ready"}',
    )

    statement = session.statements[0]
    assert "update figure_data.ai_runs" in statement
    assert "status = :status" in statement
    params = session.params[0]
    assert params is not None
    assert params["status"] == "succeeded"
    assert params["schema_valid"] is True


def test_mark_ai_run_failed_updates_error_fields() -> None:
    session = FakeSession()

    mark_ai_run_failed(
        session,  # type: ignore[arg-type]
        run_id=session.run_id,
        error_code="schema_invalid",
        error_message="bad json",
        raw_output="not json",
    )

    params = session.params[0]
    assert params is not None
    assert params["status"] == "failed"
    assert params["schema_valid"] is False
    assert params["error_code"] == "schema_invalid"


def test_get_ai_run_loads_prompt_metadata() -> None:
    session = FakeSession()

    record = get_ai_run(session, session.run_id)  # type: ignore[arg-type]

    assert record.run_id == session.run_id
    assert record.prompt_key == "ai_foundation_diagnostic"
    assert record.status == "succeeded"
