from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, status
from fastapi.requests import Request
from fastapi.responses import JSONResponse


class ErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    PERSON_NOT_FOUND = "person_not_found"
    ENCOUNTER_NOT_FOUND = "encounter_not_found"
    PERSON_AMBIGUOUS = "person_ambiguous"
    SAME_PERSON_ENDPOINT = "same_person_endpoint"
    GRAPH_NOT_SYNCED = "graph_not_synced"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    CONFIGURATION_ERROR = "configuration_error"
    AI_RESULT_NOT_FOUND = "ai_result_not_found"
    INTERNAL_ERROR = "internal_error"


ERROR_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    ErrorCode.PERSON_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.ENCOUNTER_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.PERSON_AMBIGUOUS: status.HTTP_409_CONFLICT,
    ErrorCode.SAME_PERSON_ENDPOINT: status.HTTP_400_BAD_REQUEST,
    ErrorCode.GRAPH_NOT_SYNCED: status.HTTP_409_CONFLICT,
    ErrorCode.DEPENDENCY_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.CONFIGURATION_ERROR: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.AI_RESULT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


class ApplicationError(RuntimeError):
    def __init__(
        self,
        *,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    @property
    def status_code(self) -> int:
        return ERROR_STATUS[self.code]


async def application_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, ApplicationError):
        raise exc
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code.value,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, application_error_handler)
