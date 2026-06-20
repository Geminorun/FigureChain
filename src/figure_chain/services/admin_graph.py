from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    AdminGraphBatchSummaryResponse,
    AdminGraphOperationRequest,
    AdminGraphOperationResponse,
    AdminGraphStatusResponse,
    AdminGraphSyncRequest,
    AdminOperationDetailResponse,
)
from figure_data.admin.operation_runner import run_admin_operation
from figure_data.admin.operations import (
    AdminOperationCreate,
    AdminOperationRecord,
    create_admin_operation,
    list_admin_operations,
)
from figure_data.encounters.validation import validate_encounters
from figure_data.graph.batches import get_latest_projection_batch
from figure_data.graph.projection import sync_graph_incremental, sync_graph_rebuild
from figure_data.graph.types import (
    GraphProjectionBatchRecord,
    IncrementalProjectionStats,
    ProjectionStats,
)
from figure_data.graph.validation import validate_graph
from figure_data.validation.report import ValidationCheck

LatestBatchFn = Callable[[Session, str | None], GraphProjectionBatchRecord | None]
CountEncountersFn = Callable[[Session], int]
ListOperationsFn = Callable[..., list[AdminOperationRecord]]
CreateOperationFn = Callable[[Session, AdminOperationCreate], AdminOperationRecord]
ValidateEncountersFn = Callable[[Session], list[ValidationCheck]]
ValidateGraphFn = Callable[[Session, object], list[ValidationCheck]]
SyncRebuildFn = Callable[[Session, object, str], ProjectionStats]
SyncIncrementalFn = Callable[[Session, object, str], IncrementalProjectionStats]
NowFn = Callable[[], datetime]

STALE_RUNNING_OPERATION_MINUTES = 30


class BackgroundTaskScheduler(Protocol):
    def add_task(self, func: Callable[..., Any], *args: object, **kwargs: object) -> None: ...


class AdminGraphService:
    def __init__(
        self,
        session: Session,
        *,
        session_factory: sessionmaker[Session],
        neo4j_session: object | None,
        background_tasks: BackgroundTaskScheduler,
        latest_batch_fn: LatestBatchFn | None = None,
        count_encounters_fn: Callable[..., int] | None = None,
        list_operations_fn: ListOperationsFn = list_admin_operations,
        create_operation_fn: CreateOperationFn = create_admin_operation,
        validate_encounters_fn: ValidateEncountersFn = validate_encounters,
        validate_graph_fn: ValidateGraphFn = validate_graph,
        sync_rebuild_fn: SyncRebuildFn | None = None,
        sync_incremental_fn: SyncIncrementalFn | None = None,
        now_fn: NowFn = lambda: datetime.now(UTC),
    ) -> None:
        self._session = session
        self._session_factory = session_factory
        self._neo4j_session = neo4j_session
        self._background_tasks = background_tasks
        self._latest_batch_fn = latest_batch_fn or _latest_batch
        self._count_encounters_fn = count_encounters_fn or _count_encounters
        self._list_operations_fn = list_operations_fn
        self._create_operation_fn = create_operation_fn
        self._validate_encounters_fn = validate_encounters_fn
        self._validate_graph_fn = validate_graph_fn
        self._sync_rebuild_fn = sync_rebuild_fn or _sync_rebuild
        self._sync_incremental_fn = sync_incremental_fn or _sync_incremental
        self._now_fn = now_fn

    def get_status(self) -> AdminGraphStatusResponse:
        running_operations = self._list_operations_fn(
            self._session,
            status="running",
            limit=50,
            offset=0,
        )
        return AdminGraphStatusResponse(
            latest_success=self._batch(self._latest_batch_fn(self._session, "succeeded")),
            latest_failed=self._batch(self._latest_batch_fn(self._session, "failed")),
            active_encounter_count=self._count_encounters_fn(
                self._session,
                path_eligible=False,
            ),
            path_eligible_encounter_count=self._count_encounters_fn(
                self._session,
                path_eligible=True,
            ),
            stale_running_operations=[
                self._operation(record)
                for record in running_operations
                if self._is_stale_running_operation(record)
            ],
        )

    def start_validate_encounters(
        self,
        request: AdminGraphOperationRequest,
    ) -> AdminGraphOperationResponse:
        return self._create_background_operation(
            operation_type="validate_encounters",
            actor=request.actor,
            preview="figure-data validate-encounters",
            request_payload={"actor": request.actor},
            action=lambda session: _validation_summary(self._validate_encounters_fn(session)),
        )

    def start_sync_graph(self, request: AdminGraphSyncRequest) -> AdminGraphOperationResponse:
        self._require_neo4j()
        if request.mode == "rebuild":
            return self._create_background_operation(
                operation_type="sync_graph_rebuild",
                actor=request.actor,
                preview="figure-data sync-graph --rebuild",
                request_payload={"actor": request.actor, "mode": request.mode},
                related_resource_type="graph_projection_batch",
                action=lambda session: _projection_summary(
                    self._sync_rebuild_fn(session, self._neo4j_session, request.actor)
                ),
            )
        return self._create_background_operation(
            operation_type="sync_graph_incremental",
            actor=request.actor,
            preview="figure-data sync-graph --incremental",
            request_payload={"actor": request.actor, "mode": request.mode},
            related_resource_type="graph_projection_batch",
            action=lambda session: _projection_summary(
                self._sync_incremental_fn(session, self._neo4j_session, request.actor)
            ),
        )

    def start_validate_graph(
        self,
        request: AdminGraphOperationRequest,
    ) -> AdminGraphOperationResponse:
        self._require_neo4j()
        return self._create_background_operation(
            operation_type="validate_graph",
            actor=request.actor,
            preview="figure-data validate-graph",
            request_payload={"actor": request.actor},
            related_resource_type="graph_projection_batch",
            action=lambda session: _validation_summary(
                self._validate_graph_fn(session, self._neo4j_session)
            ),
        )

    def _create_background_operation(
        self,
        *,
        operation_type: str,
        actor: str,
        preview: str,
        request_payload: dict[str, object],
        action: Callable[[Session], dict[str, object]],
        related_resource_type: str | None = None,
    ) -> AdminGraphOperationResponse:
        operation = self._create_operation_fn(
            self._session,
            AdminOperationCreate(
                operation_type=operation_type,
                actor=actor,
                request_payload=request_payload,
                related_resource_type=related_resource_type,
            ),
        )
        self._background_tasks.add_task(
            run_admin_operation,
            session_factory=self._session_factory,
            operation_id=operation.id,
            action=action,
        )
        return AdminGraphOperationResponse(
            operation_id=operation.id,
            operation_type=operation.operation_type,
            status=operation.status,
            preview=preview,
        )

    def _require_neo4j(self) -> None:
        if self._neo4j_session is None:
            raise ApplicationError(
                code=ErrorCode.CONFIGURATION_ERROR,
                message="Neo4j configuration is required",
            )

    def _is_stale_running_operation(self, record: AdminOperationRecord) -> bool:
        started_at = record.started_at or record.created_at
        return started_at <= self._now_fn() - timedelta(
            minutes=STALE_RUNNING_OPERATION_MINUTES,
        )

    def _batch(
        self,
        record: GraphProjectionBatchRecord | None,
    ) -> AdminGraphBatchSummaryResponse | None:
        if record is None:
            return None
        return AdminGraphBatchSummaryResponse(
            id=record.id,
            mode=record.mode,
            status=record.status,
            triggered_by=record.triggered_by,
            source_watermark=record.source_watermark,
            encounters_seen=record.encounters_seen,
            relationships_written=record.relationships_written,
            relationships_deleted=record.relationships_deleted,
            persons_written=record.persons_written,
            validation_status=record.validation_status,
            validation_summary=record.validation_summary,
            error_code=record.error_code,
            error_message=record.error_message,
            started_at=record.started_at,
            finished_at=record.finished_at,
        )

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


def _latest_batch(
    session: Session,
    status: str | None,
) -> GraphProjectionBatchRecord | None:
    return get_latest_projection_batch(session, status=status)


def _count_encounters(
    session: Session,
    *,
    path_eligible: bool,
) -> int:
    where = "status = 'active'"
    if path_eligible:
        where += " and path_eligible = true"
    return int(
        session.execute(
            text(f"select count(*) from figure_data.encounters where {where}")
        ).scalar_one()
    )


def _sync_rebuild(
    session: Session,
    neo4j_session: object,
    triggered_by: str,
) -> ProjectionStats:
    return sync_graph_rebuild(session, neo4j_session, triggered_by=triggered_by)  # type: ignore[arg-type]


def _sync_incremental(
    session: Session,
    neo4j_session: object,
    triggered_by: str,
) -> IncrementalProjectionStats:
    return sync_graph_incremental(session, neo4j_session, triggered_by=triggered_by)  # type: ignore[arg-type]


def _validation_summary(checks: list[ValidationCheck]) -> dict[str, object]:
    failed = [check for check in checks if not check.passed]
    return {
        "total": len(checks),
        "failed": len(failed),
        "checks": {
            check.name: {"passed": check.passed, "detail": check.detail}
            for check in checks
        },
    }


def _projection_summary(stats: ProjectionStats | IncrementalProjectionStats) -> dict[str, object]:
    summary: dict[str, object] = {
        "started_at": stats.started_at.isoformat(),
        "finished_at": stats.finished_at.isoformat(),
    }
    for key in (
        "persons_projected",
        "encounters_projected",
        "relationships_projected",
        "persons_written",
        "encounters_seen",
        "relationships_written",
        "relationships_deleted",
    ):
        if hasattr(stats, key):
            summary[key] = getattr(stats, key)
    return summary
