from __future__ import annotations

import socket
from uuid import UUID

from figure_data.ai.job_runner import execute_ai_job
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
            return result.status
        except Exception:
            session.rollback()
            raise
