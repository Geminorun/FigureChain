from datetime import UTC, datetime
from uuid import UUID

import pytest

from figure_data.ai import job_events
from figure_data.ai.job_events import NewAIJobEvent
from figure_data.ai.job_repository import AIJobEventRecord

JOB_ID = UUID("00000000-0000-0000-0000-000000000501")
EVENT_ID = UUID("00000000-0000-0000-0000-000000000701")


def test_record_ai_job_event_delegates_to_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_record_job_event(*args: object, **kwargs: object) -> UUID:
        calls.append({"args": args, "kwargs": kwargs})
        return EVENT_ID

    monkeypatch.setattr(job_events, "record_job_event", fake_record_job_event)

    session = object()
    event_id = job_events.record_ai_job_event(
        session,  # type: ignore[arg-type]
        NewAIJobEvent(
            job_id=JOB_ID,
            event_type="enqueued",
            actor="api",
            message="queued in RQ",
            metadata={"queue_name": "figure-ai"},
        ),
    )

    assert event_id == EVENT_ID
    assert calls[0]["args"] == (session,)
    assert calls[0]["kwargs"] == {
        "job_id": JOB_ID,
        "event_type": "enqueued",
        "actor": "api",
        "message": "queued in RQ",
        "metadata": {"queue_name": "figure-ai"},
    }


def test_list_ai_job_events_applies_default_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [
        AIJobEventRecord(
            id=UUID(int=index + 1),
            job_id=JOB_ID,
            event_type="progress",
            actor="worker",
            message=None,
            metadata={},
            created_at=datetime(2026, 6, 19, tzinfo=UTC),
        )
        for index in range(105)
    ]

    monkeypatch.setattr(job_events, "list_job_events", lambda session, job_id: records)

    listed = job_events.list_ai_job_events(object(), JOB_ID)  # type: ignore[arg-type]

    assert listed == records[:100]
