from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from figure_data.ai.job_repository import (
    AIGenerationJobTransitionError,
    NewAIGenerationJob,
    claim_queued_jobs,
    create_job,
    get_job,
    list_jobs_for_target,
    mark_failed,
    mark_running,
    mark_succeeded,
)

JOB_ID = UUID("00000000-0000-0000-0000-000000000501")
RESULT_ID = UUID("00000000-0000-0000-0000-000000000601")


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

    def all(self) -> list[dict[str, Any]]:
        return self.rows

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, *, transition_succeeds: bool = True) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []
        self.transition_succeeds = transition_succeeds

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> object:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params or {})
        if "insert into figure_data.ai_generation_jobs" in sql:
            return ScalarResult(JOB_ID)
        if "update figure_data.ai_generation_jobs" in sql and not self.transition_succeeds:
            return MappingResult([])
        status = (params or {}).get("status") or (params or {}).get("running_status") or "queued"
        return MappingResult([_row(status=str(status))])


def test_create_job_inserts_queued_record() -> None:
    session = FakeSession()

    job_id = create_job(
        session,  # type: ignore[arg-type]
        NewAIGenerationJob(
            job_type="candidate_review_suggestion",
            target_type="candidate",
            target_kind="relationship",
            target_id=960698,
            created_by="lyl",
            params={"language": "zh"},
        ),
    )

    assert job_id == JOB_ID
    assert "insert into figure_data.ai_generation_jobs" in session.statements[0]
    assert session.params[0]["status"] == "queued"
    assert session.params[0]["params"] == '{"language": "zh"}'


def test_get_job_loads_record() -> None:
    session = FakeSession()

    record = get_job(session, JOB_ID)  # type: ignore[arg-type]

    assert record is not None
    assert record.id == JOB_ID
    assert record.status == "queued"
    assert record.params == {"language": "zh"}


def test_list_jobs_for_target_filters_target() -> None:
    session = FakeSession()

    records = list_jobs_for_target(
        session,  # type: ignore[arg-type]
        target_type="candidate",
        target_kind="relationship",
        target_id=960698,
        limit=20,
    )

    assert records[0].id == JOB_ID
    assert "where target_type = :target_type" in session.statements[0]
    assert session.params[0]["target_id"] == 960698


def test_claim_queued_jobs_uses_skip_locked_and_marks_running() -> None:
    session = FakeSession()

    records = claim_queued_jobs(
        session,  # type: ignore[arg-type]
        limit=10,
        job_type="candidate_review_suggestion",
    )

    statement = session.statements[0].lower()
    assert records[0].id == JOB_ID
    assert records[0].status == "running"
    assert "for update skip locked" in statement
    assert "status = :running_status" in statement
    assert session.params[0]["job_type"] == "candidate_review_suggestion"


def test_mark_running_requires_queued_job() -> None:
    session = FakeSession()

    record = mark_running(session, JOB_ID)  # type: ignore[arg-type]

    assert record.status == "running"
    assert session.params[0]["expected_status"] == "queued"
    assert session.params[0]["status"] == "running"


def test_mark_succeeded_requires_running_job() -> None:
    session = FakeSession()

    mark_succeeded(
        session,  # type: ignore[arg-type]
        JOB_ID,
        result_ref_type="ai_candidate_review_suggestion",
        result_ref_id=RESULT_ID,
    )

    assert session.params[0]["expected_status"] == "running"
    assert session.params[0]["status"] == "succeeded"
    assert session.params[0]["result_ref_id"] == RESULT_ID


def test_mark_failed_requires_running_job() -> None:
    session = FakeSession()

    mark_failed(
        session,  # type: ignore[arg-type]
        JOB_ID,
        error_code="provider_unavailable",
        error_message="provider disabled",
    )

    assert session.params[0]["expected_status"] == "running"
    assert session.params[0]["status"] == "failed"
    assert session.params[0]["error_code"] == "provider_unavailable"


def test_illegal_transition_raises_clear_error() -> None:
    session = FakeSession(transition_succeeds=False)

    with pytest.raises(AIGenerationJobTransitionError):
        mark_succeeded(
            session,  # type: ignore[arg-type]
            JOB_ID,
            result_ref_type="ai_candidate_review_suggestion",
            result_ref_id=RESULT_ID,
        )


def _row(*, status: str = "queued") -> dict[str, Any]:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return {
        "id": JOB_ID,
        "job_type": "candidate_review_suggestion",
        "target_type": "candidate",
        "target_kind": "relationship",
        "target_id": 960698,
        "status": status,
        "created_by": "lyl",
        "params": {"language": "zh"},
        "result_ref_type": None,
        "result_ref_id": None,
        "error_code": None,
        "error_message": None,
        "started_at": None,
        "finished_at": None,
        "created_at": now,
        "updated_at": now,
    }
