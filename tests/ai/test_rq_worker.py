from uuid import UUID

from pytest import MonkeyPatch

from figure_data.ai.job_runner import AIGenerationJobExecutionResult
from figure_data.ai.rq_worker import _execute_with_new_session, execute_ai_job_task

JOB_ID = UUID("00000000-0000-0000-0000-000000000501")


def test_execute_ai_job_task_passes_job_id_to_executor(monkeypatch: MonkeyPatch) -> None:
    calls: list[UUID] = []

    def fake_run(job_id: UUID) -> str:
        calls.append(job_id)
        return "succeeded"

    monkeypatch.setattr("figure_data.ai.rq_worker._execute_with_new_session", fake_run)

    result = execute_ai_job_task(str(JOB_ID))

    assert result == "succeeded"
    assert calls == [JOB_ID]


def test_execute_with_new_session_schedules_rq_retry_after_commit(
    monkeypatch: MonkeyPatch,
) -> None:
    settings = type(
        "Settings",
        (),
        {
            "ai_queue_backend": "rq",
            "ai_queue_name": "figure-ai",
            "ai_job_timeout_seconds": 120,
        },
    )()
    session = FakeSession()
    queue = FakeQueue()

    monkeypatch.setattr("figure_data.ai.rq_worker.load_settings", lambda: settings)
    monkeypatch.setattr(
        "figure_data.ai.rq_worker.create_session_factory",
        lambda loaded_settings: lambda: session,
    )
    monkeypatch.setattr(
        "figure_data.ai.rq_worker.execute_ai_job",
        lambda **kwargs: AIGenerationJobExecutionResult(
            job_id=JOB_ID,
            status="retry_scheduled",
            error_code="provider_timeout",
            error_message="provider_timeout: request timed out",
            retry_delay_seconds=30,
            retry_queue_job_id_suffix="retry-1",
        ),
    )
    monkeypatch.setattr("figure_data.ai.rq_worker.create_ai_job_queue", lambda _: queue)

    result = _execute_with_new_session(JOB_ID)

    assert result == "retry_scheduled"
    assert session.commits == 1
    assert session.rollbacks == 0
    assert queue.calls == [(JOB_ID, "figure-ai", 120, 30, "retry-1")]


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str, int, int, str | None]] = []

    def enqueue(
        self,
        job_id: UUID,
        *,
        queue_name: str,
        timeout_seconds: int,
        delay_seconds: int = 0,
        queue_job_id_suffix: str | None = None,
    ) -> object:
        self.calls.append(
            (job_id, queue_name, timeout_seconds, delay_seconds, queue_job_id_suffix)
        )
        return object()
