from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol
from uuid import UUID

RQ_WORKER_TARGET = "figure_data.ai.rq_worker.execute_ai_job_task"


@dataclass(frozen=True)
class EnqueuedAIJob:
    queue_backend: str
    queue_name: str
    queue_job_id: str | None


class AIJobQueue(Protocol):
    def enqueue(
        self,
        job_id: UUID,
        *,
        queue_name: str,
        timeout_seconds: int,
        delay_seconds: int = 0,
        queue_job_id_suffix: str | None = None,
    ) -> EnqueuedAIJob:
        """Enqueue a persisted AI job by id."""


def rq_job_id(job_id: UUID, *, suffix: str | None = None) -> str:
    """Return an RQ-compatible deterministic job id for a persisted AI job."""
    base = f"figurechain-ai-job-{job_id}"
    return base if suffix is None else f"{base}-{suffix}"


class DatabaseAIJobQueue:
    def enqueue(
        self,
        job_id: UUID,
        *,
        queue_name: str,
        timeout_seconds: int,
        delay_seconds: int = 0,
        queue_job_id_suffix: str | None = None,
    ) -> EnqueuedAIJob:
        return EnqueuedAIJob(
            queue_backend="database",
            queue_name=queue_name,
            queue_job_id=None,
        )


class RQAIJobQueue:
    def __init__(self, queue: Any) -> None:
        self._queue = queue

    def enqueue(
        self,
        job_id: UUID,
        *,
        queue_name: str,
        timeout_seconds: int,
        delay_seconds: int = 0,
        queue_job_id_suffix: str | None = None,
    ) -> EnqueuedAIJob:
        queue_job_id = rq_job_id(job_id, suffix=queue_job_id_suffix)
        enqueue_kwargs = {
            "args": (str(job_id),),
            "job_id": queue_job_id,
            "timeout": timeout_seconds,
            "result_ttl": 0,
            "failure_ttl": 86400,
            "description": queue_job_id,
        }
        if delay_seconds > 0:
            rq_job = self._queue.enqueue_in(
                timedelta(seconds=delay_seconds),
                RQ_WORKER_TARGET,
                **enqueue_kwargs,
            )
        else:
            rq_job = self._queue.enqueue_call(
                func=RQ_WORKER_TARGET,
                **enqueue_kwargs,
            )
        return EnqueuedAIJob(
            queue_backend="rq",
            queue_name=queue_name,
            queue_job_id=str(rq_job.id),
        )


def create_ai_job_queue(settings: object) -> AIJobQueue:
    backend = getattr(settings, "ai_queue_backend", "database")
    if backend == "database":
        return DatabaseAIJobQueue()
    redis_url = getattr(settings, "redis_url", None)
    if not redis_url:
        raise ValueError("REDIS_URL is required when FIGURE_AI_QUEUE_BACKEND='rq'")

    from redis import Redis
    from rq import Queue

    redis_connection = Redis.from_url(str(redis_url))
    rq_queue = Queue(
        name=str(getattr(settings, "ai_queue_name", "figure-ai")),
        connection=redis_connection,
    )
    return RQAIJobQueue(rq_queue)
