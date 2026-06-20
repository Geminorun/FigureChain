from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.schemas import (
    AdminEncounterRetractResponse,
    AdminEncounterRetractResultResponse,
    AdminReviewActionResponse,
    ReviewActionResponse,
    ReviewCandidateDetailResponse,
    ReviewCandidateListResponse,
    ReviewNeedsReviewRequest,
    ReviewPromoteRequest,
    ReviewRejectRequest,
)
from figure_chain.services.review import ReviewCandidateFilters, ReviewService
from figure_data.admin.operations import (
    AdminOperationCreate,
    AdminOperationRecord,
    AdminOperationUpdate,
    create_admin_operation,
    mark_admin_operation_finished,
)
from figure_data.ai.redaction import redact_sensitive_text
from figure_data.encounters.retraction import retract_encounter
from figure_data.encounters.types import EncounterRetractionOptions, EncounterRetractionResult

CreateOperationFn = Callable[[Session, AdminOperationCreate], AdminOperationRecord]
MarkOperationFinishedFn = Callable[[Session, UUID, AdminOperationUpdate], AdminOperationRecord]
RetractEncounterFn = Callable[[Session, EncounterRetractionOptions], EncounterRetractionResult]


class ReviewServiceBackend(Protocol):
    def list_candidates(self, filters: ReviewCandidateFilters) -> ReviewCandidateListResponse: ...

    def get_candidate(self, kind: str, candidate_id: int) -> ReviewCandidateDetailResponse: ...

    def promote_candidate(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewPromoteRequest,
    ) -> ReviewActionResponse: ...

    def reject_candidate(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewRejectRequest,
    ) -> ReviewActionResponse: ...

    def mark_candidate_needs_review(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewNeedsReviewRequest,
    ) -> ReviewActionResponse: ...


class AdminReviewService:
    def __init__(
        self,
        session: Session,
        *,
        review_service: ReviewServiceBackend | None = None,
        retract_encounter_fn: RetractEncounterFn | None = None,
        create_operation_fn: CreateOperationFn = create_admin_operation,
        mark_operation_finished_fn: MarkOperationFinishedFn = mark_admin_operation_finished,
    ) -> None:
        self._session = session
        self._review_service = review_service or ReviewService(session)
        self._retract_encounter_fn = retract_encounter_fn or retract_encounter
        self._create_operation_fn = create_operation_fn
        self._mark_operation_finished_fn = mark_operation_finished_fn

    def list_candidates(self, filters: ReviewCandidateFilters) -> ReviewCandidateListResponse:
        return self._review_service.list_candidates(filters)

    def get_candidate(self, kind: str, candidate_id: int) -> ReviewCandidateDetailResponse:
        return self._review_service.get_candidate(kind, candidate_id)

    def promote_candidate(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewPromoteRequest,
    ) -> AdminReviewActionResponse:
        return self._candidate_action(
            operation_type="promote_candidate",
            kind=kind,
            candidate_id=candidate_id,
            actor=request.reviewed_by,
            request_payload=request.model_dump(mode="json"),
            preview=(
                f"figure-data promote-encounter --kind {kind} --id {candidate_id} "
                f"--reviewed-by {request.reviewed_by}"
            ),
            action=lambda: self._review_service.promote_candidate(kind, candidate_id, request),
        )

    def reject_candidate(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewRejectRequest,
    ) -> AdminReviewActionResponse:
        return self._candidate_action(
            operation_type="reject_candidate",
            kind=kind,
            candidate_id=candidate_id,
            actor=request.reviewed_by,
            request_payload=request.model_dump(mode="json"),
            preview=(
                f"figure-data reject-candidate --kind {kind} --id {candidate_id} "
                f"--reviewed-by {request.reviewed_by}"
            ),
            action=lambda: self._review_service.reject_candidate(kind, candidate_id, request),
        )

    def mark_candidate_needs_review(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewNeedsReviewRequest,
    ) -> AdminReviewActionResponse:
        return self._candidate_action(
            operation_type="mark_candidate_needs_review",
            kind=kind,
            candidate_id=candidate_id,
            actor=request.reviewed_by,
            request_payload=request.model_dump(mode="json"),
            preview=(
                f"figure-data mark-candidate-review --kind {kind} --id {candidate_id} "
                f"--reviewed-by {request.reviewed_by}"
            ),
            action=lambda: self._review_service.mark_candidate_needs_review(
                kind,
                candidate_id,
                request,
            ),
        )

    def retract_encounter(
        self,
        encounter_id: UUID,
        *,
        reviewed_by: str,
        note: str,
        force: bool = False,
    ) -> AdminEncounterRetractResponse:
        operation = self._create_operation(
            operation_type="retract_encounter",
            actor=reviewed_by,
            request_payload={
                "encounter_id": str(encounter_id),
                "reviewed_by": reviewed_by,
                "note": note,
                "force": force,
            },
            related_resource_type="encounter",
            related_resource_id=str(encounter_id),
        )
        _commit_if_supported(self._session)
        preview = (
            f"figure-data retract-encounter --encounter-id {encounter_id} "
            f"--reviewed-by {reviewed_by}"
        )
        try:
            result = self._retract_encounter_fn(
                self._session,
                EncounterRetractionOptions(
                    encounter_id=encounter_id,
                    reviewed_by=reviewed_by,
                    note=note,
                    force=force,
                ),
            )
            response_result = AdminEncounterRetractResultResponse(
                encounter_id=result.encounter_id,
                status=result.status.value,
                path_eligible=result.path_eligible,
                linked_candidates_updated=result.linked_candidates_updated,
            )
            summary = response_result.model_dump(mode="json")
            finished = self._finish_operation(
                operation.id,
                status="succeeded",
                summary=summary,
            )
            return AdminEncounterRetractResponse(
                operation_id=operation.id,
                operation_type=operation.operation_type,
                status=finished.status,
                result=response_result,
                preview=preview,
            )
        except Exception as exc:
            _rollback_if_supported(self._session)
            self._finish_failed_operation(operation.id, exc)
            _commit_if_supported(self._session)
            raise

    def _candidate_action(
        self,
        *,
        operation_type: str,
        kind: str,
        candidate_id: int,
        actor: str,
        request_payload: dict[str, object],
        preview: str,
        action: Callable[[], ReviewActionResponse],
    ) -> AdminReviewActionResponse:
        operation = self._create_operation(
            operation_type=operation_type,
            actor=actor,
            request_payload={"kind": kind, "candidate_id": candidate_id, **request_payload},
            related_resource_type="candidate",
            related_resource_id=f"{kind}:{candidate_id}",
        )
        _commit_if_supported(self._session)
        try:
            result = action()
            summary = {
                "kind": result.kind,
                "candidate_id": result.candidate_id,
                "status": result.status,
                "reviewed_by": result.reviewed_by,
                "encounter_id": (
                    str(result.encounter.encounter_id)
                    if result.encounter is not None
                    else None
                ),
            }
            finished = self._finish_operation(
                operation.id,
                status="succeeded",
                summary=summary,
            )
            return AdminReviewActionResponse(
                operation_id=operation.id,
                operation_type=operation.operation_type,
                status=finished.status,
                action=result,
                preview=preview,
            )
        except Exception as exc:
            _rollback_if_supported(self._session)
            self._finish_failed_operation(operation.id, exc)
            _commit_if_supported(self._session)
            raise

    def _create_operation(
        self,
        *,
        operation_type: str,
        actor: str,
        request_payload: dict[str, object],
        related_resource_type: str,
        related_resource_id: str | None,
    ) -> AdminOperationRecord:
        return self._create_operation_fn(
            self._session,
            AdminOperationCreate(
                operation_type=operation_type,
                actor=actor,
                request_payload=request_payload,
                related_resource_type=related_resource_type,
                related_resource_id=related_resource_id,
            ),
        )

    def _finish_operation(
        self,
        operation_id: UUID,
        *,
        status: str,
        summary: dict[str, object],
    ) -> AdminOperationRecord:
        return self._mark_operation_finished_fn(
            self._session,
            operation_id,
            AdminOperationUpdate(status=status, result_summary=summary),
        )

    def _finish_failed_operation(self, operation_id: UUID, exc: Exception) -> AdminOperationRecord:
        return self._mark_operation_finished_fn(
            self._session,
            operation_id,
            AdminOperationUpdate(
                status="failed",
                result_summary={},
                error_message=redact_sensitive_text(str(exc)),
            ),
        )


def _commit_if_supported(session: Session) -> None:
    commit = getattr(session, "commit", None)
    if callable(commit):
        commit()


def _rollback_if_supported(session: Session) -> None:
    rollback = getattr(session, "rollback", None)
    if callable(rollback):
        rollback()
