from uuid import UUID

from figure_data.ai.queue import DatabaseAIJobQueue, RQAIJobQueue

JOB_ID = UUID("00000000-0000-0000-0000-000000000501")


class FakeRQJob:
    id = "rq-job-501"


class FakeRQQueue:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def enqueue_call(self, **kwargs: object) -> FakeRQJob:
        self.calls.append(kwargs)
        return FakeRQJob()


def test_database_queue_does_not_enqueue_to_redis() -> None:
    queue = DatabaseAIJobQueue()

    result = queue.enqueue(JOB_ID, queue_name="figure-ai", timeout_seconds=120)

    assert result.queue_backend == "database"
    assert result.queue_name == "figure-ai"
    assert result.queue_job_id is None


def test_rq_queue_enqueues_only_job_id() -> None:
    fake_queue = FakeRQQueue()
    queue = RQAIJobQueue(fake_queue)

    result = queue.enqueue(JOB_ID, queue_name="figure-ai", timeout_seconds=120)

    assert result.queue_backend == "rq"
    assert result.queue_job_id == "rq-job-501"
    assert fake_queue.calls[0]["args"] == (str(JOB_ID),)
    assert fake_queue.calls[0]["func"] == "figure_data.ai.rq_worker.execute_ai_job_task"
    assert fake_queue.calls[0]["job_id"] == f"figurechain-ai-job:{JOB_ID}"
