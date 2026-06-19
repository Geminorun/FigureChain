from uuid import UUID

from figure_data.ai.rq_worker import execute_ai_job_task

JOB_ID = UUID("00000000-0000-0000-0000-000000000501")


def test_execute_ai_job_task_passes_job_id_to_executor(monkeypatch) -> None:
    calls: list[UUID] = []

    def fake_run(job_id: UUID) -> str:
        calls.append(job_id)
        return "succeeded"

    monkeypatch.setattr("figure_data.ai.rq_worker._execute_with_new_session", fake_run)

    result = execute_ai_job_task(str(JOB_ID))

    assert result == "succeeded"
    assert calls == [JOB_ID]
