from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import AdminOperationDetailResponse, AdminOperationListResponse
from figure_data.admin.operations import (
    AdminOperationNotFoundError,
    AdminOperationRecord,
    get_admin_operation,
    list_admin_operations,
)

ListAdminOperationsFn = Callable[..., list[AdminOperationRecord]]
GetAdminOperationFn = Callable[[Session, UUID], AdminOperationRecord]


@dataclass(frozen=True)
class AdminOperationFilters:
    status: str | None = None
    operation_type: str | None = None
    actor: str | None = None
    limit: int = 50
    offset: int = 0


class AdminService:
    def __init__(
        self,
        session: Session,
        *,
        list_operations_fn: ListAdminOperationsFn = list_admin_operations,
        get_operation_fn: GetAdminOperationFn = get_admin_operation,
    ) -> None:
        self._session = session
        self._list_operations_fn = list_operations_fn
        self._get_operation_fn = get_operation_fn

    def list_operations(self, filters: AdminOperationFilters) -> AdminOperationListResponse:
        records = self._list_operations_fn(
            self._session,
            status=filters.status,
            operation_type=filters.operation_type,
            actor=filters.actor,
            limit=filters.limit,
            offset=filters.offset,
        )
        return AdminOperationListResponse(
            items=[self._operation(record) for record in records],
            limit=filters.limit,
            offset=filters.offset,
            count=len(records),
        )

    def get_operation(self, operation_id: UUID) -> AdminOperationDetailResponse:
        try:
            record = self._get_operation_fn(self._session, operation_id)
        except AdminOperationNotFoundError as exc:
            raise ApplicationError(
                code=ErrorCode.ADMIN_OPERATION_NOT_FOUND,
                message="admin operation was not found",
                details={"operation_id": str(operation_id)},
            ) from exc
        return self._operation(record)

    def _operation(self, record: AdminOperationRecord) -> AdminOperationDetailResponse:
        return AdminOperationDetailResponse(
            operation_id=record.id,
            operation_type=record.operation_type,
            actor=record.actor,
            status=record.status,
            request_payload=record.request_payload,
            result_summary=record.result_summary,
            error_message=record.error_message,
            related_resource_type=record.related_resource_type,
            related_resource_id=record.related_resource_id,
            started_at=record.started_at,
            finished_at=record.finished_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
