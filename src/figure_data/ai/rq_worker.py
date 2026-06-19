from __future__ import annotations

import socket
from uuid import UUID

from figure_data.ai.job_runner import execute_ai_job
from figure_data.ai.queue import create_ai_job_queue
from figure_data.config import load_settings
from figure_data.db.session import create_session_factory


def execute_ai_job_task(job_id: str) -> str:
    """RQ entrypoint for executing one persisted AI job."""
    return _execute_with_new_session(UUID(job_id))


def _execute_with_new_session(job_id: UUID) -> str:
    settings = load_settings()
    factory = create_session_factory(settings)
    worker_id = socket.gethostname()
    with factory() as session:
        try:
            result = execute_ai_job(
                session=session,
                settings=settings,
                job_id=job_id,
                worker_id=worker_id,
            )
            session.commit()
            _enqueue_retry_if_scheduled(settings, job_id, result)
            return result.status
        except Exception:
            session.rollback()
            raise


def _enqueue_retry_if_scheduled(settings: object, job_id: UUID, result: object) -> None:
    if getattr(result, "status", None) != "retry_scheduled":
        return
    delay_seconds = getattr(result, "retry_delay_seconds", None)
    if delay_seconds is None:
        return
    if getattr(settings, "ai_queue_backend", "database") != "rq":
        return

    queue = create_ai_job_queue(settings)
    queue.enqueue(
        job_id,
        queue_name=str(getattr(settings, "ai_queue_name", "figure-ai")),
        timeout_seconds=int(getattr(settings, "ai_job_timeout_seconds", 120)),
        delay_seconds=int(delay_seconds),
        queue_job_id_suffix=getattr(result, "retry_queue_job_id_suffix", None),
    )
