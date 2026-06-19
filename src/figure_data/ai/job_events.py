from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.ai.job_repository import AIJobEventRecord, list_job_events, record_job_event

DEFAULT_EVENT_LIMIT = 100


@dataclass(frozen=True)
class NewAIJobEvent:
    job_id: UUID
    event_type: str
    actor: str
    message: str | None = None
    metadata: dict[str, Any] | None = None


def record_ai_job_event(session: Session, event: NewAIJobEvent) -> UUID:
    return record_job_event(
        session,
        job_id=event.job_id,
        event_type=event.event_type,
        actor=event.actor,
        message=event.message,
        metadata=event.metadata,
    )


def list_ai_job_events(
    session: Session,
    job_id: UUID,
    *,
    limit: int = DEFAULT_EVENT_LIMIT,
) -> list[AIJobEventRecord]:
    return list_job_events(session, job_id)[:limit]
