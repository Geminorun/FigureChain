from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.admin.operations import (
    AdminOperationUpdate,
    mark_admin_operation_finished,
    mark_admin_operation_running,
)
from figure_data.ai.redaction import redact_sensitive_text

SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b(token|password|secret|api_key|apikey)=\S+",
    re.IGNORECASE,
)


def run_admin_operation(
    *,
    session_factory: Callable[[], Session],
    operation_id: UUID,
    action: Callable[[Session], dict[str, object]],
    mark_running_fn: Callable[[Any, UUID], object] = mark_admin_operation_running,
    mark_finished_fn: Callable[..., object] | None = None,
) -> None:
    finish_operation = mark_finished_fn or _mark_finished
    session = session_factory()
    try:
        mark_running_fn(session, operation_id)
        session.commit()

        result_summary = action(session)
        finish_operation(
            session,
            operation_id,
            status="succeeded",
            result_summary=result_summary,
            error_message=None,
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        finish_operation(
            session,
            operation_id,
            status="failed",
            result_summary={},
            error_message=_redact_error_message(exc),
        )
        session.commit()
    finally:
        close = getattr(session, "close", None)
        if callable(close):
            close()


def _mark_finished(
    session: Session,
    operation_id: UUID,
    *,
    status: str,
    result_summary: dict[str, object] | None = None,
    error_message: str | None = None,
) -> None:
    mark_admin_operation_finished(
        session,
        operation_id,
        AdminOperationUpdate(
            status=status,
            result_summary=result_summary or {},
            error_message=error_message,
        ),
    )


def _redact_error_message(exc: Exception) -> str:
    redacted = redact_sensitive_text(str(exc))
    return SECRET_ASSIGNMENT_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", redacted)
