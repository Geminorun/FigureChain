from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
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
    ) -> EnqueuedAIJob:
        """Enqueue a persisted AI job by id."""


class _RQQueueLike(Protocol):
    def enqueue_call(self, **kwargs: object) -> object:
        """Subset of rq.Queue used by the adapter."""


class DatabaseAIJobQueue:
    def enqueue(
        self,
        job_id: UUID,
        *,
        queue_name: str,
        timeout_seconds: int,
    ) -> EnqueuedAIJob:
        return EnqueuedAIJob(
            queue_backend="database",
            queue_name=queue_name,
            queue_job_id=None,
        )


class RQAIJobQueue:
    def __init__(self, queue: _RQQueueLike) -> None:
        self._queue = queue

    def enqueue(
        self,
        job_id: UUID,
        *,
        queue_name: str,
        timeout_seconds: int,
    ) -> EnqueuedAIJob:
        rq_job = self._queue.enqueue_call(
            func=RQ_WORKER_TARGET,
            args=(str(job_id),),
            job_id=f"figurechain-ai-job:{job_id}",
            timeout=timeout_seconds,
            result_ttl=0,
            failure_ttl=86400,
            description=f"figurechain-ai-job:{job_id}",
        )
        return EnqueuedAIJob(
            queue_backend="rq",
            queue_name=queue_name,
            queue_job_id=str(getattr(rq_job, "id")),
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
