from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    ReviewActionResponse,
    ReviewCandidateDetailResponse,
    ReviewCandidateListResponse,
    ReviewCandidatePersonResponse,
    ReviewCandidateRelationResponse,
    ReviewCandidateTimeResponse,
    ReviewLinkedEncounterResponse,
    ReviewNeedsReviewRequest,
    ReviewPromoteRequest,
    ReviewPromotionReadinessResponse,
    ReviewRejectRequest,
)
from figure_chain.services.admin_review import AdminReviewService
from figure_chain.services.review import ReviewCandidateFilters
from figure_data.admin.operations import (
    AdminOperationCreate,
    AdminOperationRecord,
    AdminOperationUpdate,
)
from figure_data.db.enums import EncounterStatus
from figure_data.encounters.types import EncounterRetractionOptions, EncounterRetractionResult

NOW = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
OPERATION_ID = UUID("00000000-0000-0000-0000-000000000901")
ENCOUNTER_ID = UUID("00000000-0000-0000-0000-000000000003")


class FakeReviewService:
    def __init__(self, *, fail_action: bool = False) -> None:
        self.fail_action = fail_action
        self.listed: list[ReviewCandidateFilters] = []
        self.promoted: list[tuple[str, int, str]] = []
        self.rejected: list[tuple[str, int, str]] = []
        self.marked: list[tuple[str, int, str]] = []

    def list_candidates(self, filters: ReviewCandidateFilters) -> ReviewCandidateListResponse:
        self.listed.append(filters)
        return ReviewCandidateListResponse(
            items=[],
            limit=filters.limit,
            offset=filters.offset,
            count=0,
        )

    def get_candidate(self, kind: str, candidate_id: int) -> ReviewCandidateDetailResponse:
        return _detail(kind=kind, candidate_id=candidate_id)

    def promote_candidate(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewPromoteRequest,
    ) -> ReviewActionResponse:
        if self.fail_action:
            raise ApplicationError(code=ErrorCode.INVALID_REQUEST, message="promotion failed")
        self.promoted.append((kind, candidate_id, request.reviewed_by))
        return _action(kind=kind, candidate_id=candidate_id, status="promoted_to_encounter")

    def reject_candidate(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewRejectRequest,
    ) -> ReviewActionResponse:
        self.rejected.append((kind, candidate_id, request.reviewed_by))
        return _action(kind=kind, candidate_id=candidate_id, status="rejected")

    def mark_candidate_needs_review(
        self,
        kind: str,
        candidate_id: int,
        request: ReviewNeedsReviewRequest,
    ) -> ReviewActionResponse:
        self.marked.append((kind, candidate_id, request.reviewed_by))
        return _action(kind=kind, candidate_id=candidate_id, status="needs_review")


def test_admin_review_service_lists_candidates_through_review_service() -> None:
    review_service = FakeReviewService()
    service = _service(review_service=review_service)

    response = service.list_candidates(ReviewCandidateFilters(kind="relationship", limit=25))

    assert response.count == 0
    assert review_service.listed == [ReviewCandidateFilters(kind="relationship", limit=25)]


def test_admin_review_service_gets_candidate_through_review_service() -> None:
    service = _service(review_service=FakeReviewService())

    response = service.get_candidate("relationship", 960655)

    assert response.kind == "relationship"
    assert response.candidate_id == 960655


def test_admin_review_service_records_promote_operation() -> None:
    review_service = FakeReviewService()
    created: list[AdminOperationCreate] = []
    finished: list[AdminOperationUpdate] = []
    service = _service(review_service=review_service, created=created, finished=finished)

    response = service.promote_candidate(
        "relationship",
        960655,
        ReviewPromoteRequest(reviewed_by="local", evidence_summary="证据摘要"),
    )

    assert created[0].operation_type == "promote_candidate"
    assert created[0].related_resource_type == "candidate"
    assert created[0].related_resource_id == "relationship:960655"
    assert finished[0].status == "succeeded"
    assert review_service.promoted == [("relationship", 960655, "local")]
    assert response.operation_id == OPERATION_ID
    assert response.preview == (
        "figure-data promote-encounter --kind relationship --id 960655 --reviewed-by local"
    )


def test_admin_review_service_records_reject_operation() -> None:
    review_service = FakeReviewService()
    created: list[AdminOperationCreate] = []
    service = _service(review_service=review_service, created=created)

    response = service.reject_candidate(
        "relationship",
        960655,
        ReviewRejectRequest(reviewed_by="local", reason="证据不足"),
    )

    assert created[0].operation_type == "reject_candidate"
    assert review_service.rejected == [("relationship", 960655, "local")]
    assert response.preview == (
        "figure-data reject-candidate --kind relationship --id 960655 --reviewed-by local"
    )


def test_admin_review_service_records_needs_review_operation() -> None:
    review_service = FakeReviewService()
    created: list[AdminOperationCreate] = []
    service = _service(review_service=review_service, created=created)

    response = service.mark_candidate_needs_review(
        "relationship",
        960655,
        ReviewNeedsReviewRequest(reviewed_by="local", note="待查"),
    )

    assert created[0].operation_type == "mark_candidate_needs_review"
    assert review_service.marked == [("relationship", 960655, "local")]
    assert response.preview == (
        "figure-data mark-candidate-review --kind relationship --id 960655 --reviewed-by local"
    )


def test_admin_review_service_records_retract_operation() -> None:
    captured_options: list[EncounterRetractionOptions] = []
    created: list[AdminOperationCreate] = []
    finished: list[AdminOperationUpdate] = []

    def retract_fn(
        session: Session,
        options: EncounterRetractionOptions,
    ) -> EncounterRetractionResult:
        captured_options.append(options)
        return EncounterRetractionResult(
            encounter_id=options.encounter_id,
            status=EncounterStatus.RETRACTED,
            path_eligible=False,
            linked_candidates_updated=2,
        )

    service = _service(
        review_service=FakeReviewService(),
        created=created,
        finished=finished,
        retract_encounter_fn=retract_fn,
    )

    response = service.retract_encounter(
        ENCOUNTER_ID,
        reviewed_by="local",
        note="证据不足",
        force=True,
    )

    assert created[0].operation_type == "retract_encounter"
    assert created[0].related_resource_type == "encounter"
    assert created[0].related_resource_id == str(ENCOUNTER_ID)
    assert captured_options[0].force is True
    assert finished[0].status == "succeeded"
    assert response.result.linked_candidates_updated == 2
    assert response.preview == (
        f"figure-data retract-encounter --encounter-id {ENCOUNTER_ID} --reviewed-by local"
    )


def test_admin_review_service_marks_operation_failed_when_action_fails() -> None:
    created: list[AdminOperationCreate] = []
    finished: list[AdminOperationUpdate] = []
    service = _service(
        review_service=FakeReviewService(fail_action=True),
        created=created,
        finished=finished,
    )

    with pytest.raises(ApplicationError):
        service.promote_candidate(
            "relationship",
            960655,
            ReviewPromoteRequest(reviewed_by="local", evidence_summary="证据摘要"),
        )

    assert created[0].operation_type == "promote_candidate"
    assert finished[0].status == "failed"
    assert finished[0].error_message == "promotion failed"


def _service(
    *,
    review_service: FakeReviewService,
    created: list[AdminOperationCreate] | None = None,
    finished: list[AdminOperationUpdate] | None = None,
    retract_encounter_fn: Any | None = None,
) -> AdminReviewService:
    created = created if created is not None else []
    finished = finished if finished is not None else []

    def create_operation(
        session: Session,
        operation: AdminOperationCreate,
    ) -> AdminOperationRecord:
        created.append(operation)
        return _operation(
            operation.operation_type,
            related_resource_id=operation.related_resource_id,
        )

    def mark_finished(
        session: Session,
        operation_id: UUID,
        update: AdminOperationUpdate,
    ) -> AdminOperationRecord:
        finished.append(update)
        return _operation("finished", status=update.status, result_summary=update.result_summary)

    return AdminReviewService(
        cast(Session, object()),
        review_service=review_service,
        create_operation_fn=create_operation,
        mark_operation_finished_fn=mark_finished,
        retract_encounter_fn=retract_encounter_fn,
    )


def _operation(
    operation_type: str,
    *,
    status: str = "queued",
    result_summary: dict[str, Any] | None = None,
    related_resource_id: str | None = "relationship:960655",
) -> AdminOperationRecord:
    return AdminOperationRecord(
        id=OPERATION_ID,
        operation_type=operation_type,
        actor="local",
        status=status,
        request_payload={},
        result_summary=result_summary or {},
        error_message=None,
        related_resource_type="candidate",
        related_resource_id=related_resource_id,
        started_at=None,
        finished_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _action(*, kind: str, candidate_id: int, status: str) -> ReviewActionResponse:
    return ReviewActionResponse(
        kind=kind,
        candidate_id=candidate_id,
        status=status,
        reviewed_by="local",
        encounter=(
            ReviewLinkedEncounterResponse(encounter_id=ENCOUNTER_ID, status="active")
            if status == "promoted_to_encounter"
            else None
        ),
        message=None,
    )


def _detail(*, kind: str, candidate_id: int) -> ReviewCandidateDetailResponse:
    person = ReviewCandidatePersonResponse(
        person_id=None,
        cbdb_id=780,
        display_name="許幾",
        primary_name_zh_hant="許幾",
        primary_name_zh_hans=None,
        primary_name_romanized=None,
        birth_year=None,
        death_year=None,
    )
    return ReviewCandidateDetailResponse(
        kind=kind,
        candidate_id=candidate_id,
        person_a=person,
        person_b=person,
        relation=ReviewCandidateRelationResponse(
            relation_type="同僚",
            basis="direct_interaction_likely",
            strength="high",
            notes=None,
            source_name=None,
            source_table=None,
            source_pk=None,
        ),
        time=ReviewCandidateTimeResponse(summary=None, pages=None),
        place=None,
        status="unreviewed",
        confidence=0.9,
        source_refs=[],
        evidence=[],
        promotion_readiness=ReviewPromotionReadinessResponse(
            default_promotable=True,
            default_path_eligible=True,
            reasons=[],
        ),
        linked_encounter=None,
        latest_ai_suggestion=None,
        ai_jobs=[],
    )
