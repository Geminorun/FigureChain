from dataclasses import dataclass, field
from uuid import UUID, uuid4

from figure_data.admin.operation_runner import run_admin_operation


@dataclass
class FakeSession:
    committed: int = 0
    rolled_back: int = 0

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        self.rolled_back += 1


@dataclass
class FakeFactory:
    session: FakeSession = field(default_factory=FakeSession)

    def __call__(self) -> FakeSession:
        return self.session


def test_run_admin_operation_marks_success() -> None:
    operation_id = uuid4()
    events: list[tuple[str, UUID, dict[str, object] | None]] = []

    def mark_running(session: object, op_id: UUID) -> None:
        events.append(("running", op_id, None))

    def mark_finished(
        session: object,
        op_id: UUID,
        *,
        status: str,
        result_summary: dict[str, object] | None = None,
        error_message: str | None = None,
    ) -> None:
        events.append((status, op_id, result_summary))

    def action(session: object) -> dict[str, object]:
        return {"checks": 8, "failed": 0}

    factory = FakeFactory()
    run_admin_operation(
        session_factory=factory,  # type: ignore[arg-type]
        operation_id=operation_id,
        action=action,
        mark_running_fn=mark_running,
        mark_finished_fn=mark_finished,
    )

    assert events == [
        ("running", operation_id, None),
        ("succeeded", operation_id, {"checks": 8, "failed": 0}),
    ]
    assert factory.session.committed == 2


def test_run_admin_operation_marks_failure_with_redacted_message() -> None:
    operation_id = uuid4()
    statuses: list[str] = []
    errors: list[str | None] = []

    def mark_running(session: object, op_id: UUID) -> None:
        statuses.append("running")

    def mark_finished(
        session: object,
        op_id: UUID,
        *,
        status: str,
        result_summary: dict[str, object] | None = None,
        error_message: str | None = None,
    ) -> None:
        statuses.append(status)
        errors.append(error_message)

    def action(session: object) -> dict[str, object]:
        raise RuntimeError("provider token=secret-value failed")

    run_admin_operation(
        session_factory=FakeFactory(),  # type: ignore[arg-type]
        operation_id=operation_id,
        action=action,
        mark_running_fn=mark_running,
        mark_finished_fn=mark_finished,
    )

    assert statuses == ["running", "failed"]
    assert errors == ["provider token=[REDACTED] failed"]
