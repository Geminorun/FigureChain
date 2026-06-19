from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import ReviewNeedsReviewRequest, ReviewPromoteRequest, ReviewRejectRequest
from figure_chain.services.review import ReviewCandidateFilters, ReviewService
from figure_data.ai.candidate_repository import (
    CandidateSuggestionListFilters,
    CandidateSuggestionRecord,
)
from figure_data.ai.job_repository import AIGenerationJobRecord
from figure_data.encounters.types import (
    EncounterOperationError,
    EncounterPromotionOptions,
    EncounterPromotionResult,
)
from figure_data.review.candidate_listing import CandidateListFilters
from figure_data.review.types import (
    CandidateDetail,
    CandidateKind,
    CandidatePerson,
    CandidateReviewError,
    CandidateReviewStatus,
    CandidateSourceRef,
    CandidateStatusChange,
    CandidateSummary,
    PromotionReadiness,
)

PERSON_A_ID = UUID("00000000-0000-0000-0000-000000000001")
PERSON_B_ID = UUID("00000000-0000-0000-0000-000000000002")
ENCOUNTER_ID = UUID("00000000-0000-0000-0000-000000000003")


def test_review_service_maps_relationship_and_kinship_summaries() -> None:
    captured_filters: list[CandidateListFilters] = []

    def list_fn(session: Session, filters: CandidateListFilters) -> list[CandidateSummary]:
        captured_filters.append(filters)
        return [
            _summary(CandidateKind.RELATIONSHIP, 10, "同僚"),
            _summary(CandidateKind.KINSHIP, 11, "父子"),
        ]

    service = _service(list_summaries_fn=list_fn)

    response = service.list_candidates(
        ReviewCandidateFilters(kind=None, status="unreviewed", limit=50, offset=0)
    )

    assert captured_filters[0].review_status == "unreviewed"
    assert response.count == 2
    assert [item.kind for item in response.items] == ["relationship", "kinship"]
    assert response.items[0].person_a.person_id == str(PERSON_A_ID)
    assert response.items[0].confidence == 0.9
    assert response.items[0].promotion_readiness.default_promotable is True
    assert response.items[1].promotion_readiness.default_promotable is False


def test_review_service_filters_summary_by_person_and_confidence() -> None:
    captured_filters: list[CandidateListFilters] = []

    def list_fn(session: Session, filters: CandidateListFilters) -> list[CandidateSummary]:
        captured_filters.append(filters)
        return [
            _summary(CandidateKind.RELATIONSHIP, 10, "同僚", strength="high"),
        ]

    service = _service(list_summaries_fn=list_fn)

    response = service.list_candidates(
        ReviewCandidateFilters(
            kind="relationship",
            person_id=PERSON_A_ID,
            min_confidence=0.8,
            limit=50,
            offset=0,
        )
    )

    assert response.count == 1
    assert response.items[0].candidate_id == 10
    assert captured_filters[0].person_id == PERSON_A_ID
    assert captured_filters[0].min_confidence == 0.8
    assert captured_filters[0].limit == 50
    assert captured_filters[0].offset == 0


def test_review_service_passes_offset_to_candidate_listing() -> None:
    captured_filters: list[CandidateListFilters] = []

    def list_fn(session: Session, filters: CandidateListFilters) -> list[CandidateSummary]:
        captured_filters.append(filters)
        return [
            _summary(CandidateKind.RELATIONSHIP, 11, "同僚"),
        ]

    service = _service(list_summaries_fn=list_fn)

    response = service.list_candidates(ReviewCandidateFilters(limit=1, offset=1))

    assert response.count == 1
    assert response.items[0].candidate_id == 11
    assert captured_filters[0].limit == 1
    assert captured_filters[0].offset == 1


def test_review_service_returns_empty_list() -> None:
    service = _service(
        list_summaries_fn=lambda session, filters: [],
    )

    response = service.list_candidates(ReviewCandidateFilters(limit=50, offset=0))

    assert response.items == []
    assert response.count == 0


def test_review_service_maps_candidate_detail_with_stable_empty_ai_fields() -> None:
    def detail_fn(session: Session, kind: CandidateKind, candidate_id: int) -> CandidateDetail:
        assert kind is CandidateKind.RELATIONSHIP
        assert candidate_id == 10
        return _detail(kind, candidate_id)

    service = _service(get_detail_fn=detail_fn)

    response = service.get_candidate("relationship", 10)

    assert response.kind == "relationship"
    assert response.person_a.display_name == "許幾"
    assert response.relation.relation_type == "同僚"
    assert response.source_refs[0].source_ref_id == 100
    assert response.promotion_readiness.reasons == []
    assert response.linked_encounter is not None
    assert response.linked_encounter.encounter_id == ENCOUNTER_ID
    assert response.latest_ai_suggestion is None
    assert response.ai_jobs == []


def test_review_service_maps_ai_job_and_suggestion_fields() -> None:
    captured_job_targets: list[tuple[str, str, int, int]] = []
    captured_suggestion_filters: list[CandidateSuggestionListFilters] = []

    def detail_fn(session: Session, kind: CandidateKind, candidate_id: int) -> CandidateDetail:
        return _detail(kind, candidate_id)

    def list_jobs_fn(
        session: Session,
        *,
        target_type: str,
        target_kind: str,
        target_id: int,
        limit: int,
    ) -> list[AIGenerationJobRecord]:
        captured_job_targets.append((target_type, target_kind, target_id, limit))
        return [_job_record(status="succeeded")]

    def list_suggestions_fn(
        session: Session,
        filters: CandidateSuggestionListFilters,
    ) -> list[CandidateSuggestionRecord]:
        captured_suggestion_filters.append(filters)
        return [_suggestion_record()]

    service = ReviewService(
        cast(Session, object()),
        list_summaries_fn=lambda session, filters: [
            _summary(CandidateKind.RELATIONSHIP, 10, "同僚")
        ],
        get_detail_fn=detail_fn,
        list_ai_jobs_fn=list_jobs_fn,
        list_suggestions_fn=list_suggestions_fn,
    )

    list_response = service.list_candidates(ReviewCandidateFilters(kind="relationship"))
    detail_response = service.get_candidate("relationship", 10)

    assert list_response.items[0].latest_ai_job_status == "succeeded"
    assert list_response.items[0].has_ai_suggestion is True
    assert detail_response.latest_ai_suggestion is not None
    assert detail_response.latest_ai_suggestion.recommendation == "promote"
    assert detail_response.latest_ai_suggestion.summary == "证据支持二人直接见面。"
    assert detail_response.ai_jobs[0].status == "succeeded"
    assert captured_job_targets == [
        ("candidate", "relationship", 10, 1),
        ("candidate", "relationship", 10, 20),
    ]
    assert captured_suggestion_filters == [
        CandidateSuggestionListFilters(
            candidate_kind=CandidateKind.RELATIONSHIP,
            candidate_id=10,
            limit=1,
        ),
        CandidateSuggestionListFilters(
            candidate_kind=CandidateKind.RELATIONSHIP,
            candidate_id=10,
            limit=1,
        ),
    ]


def test_review_service_maps_missing_candidate_to_application_error() -> None:
    def detail_fn(session: Session, kind: CandidateKind, candidate_id: int) -> CandidateDetail:
        raise CandidateReviewError("candidate not found")

    service = _service(get_detail_fn=detail_fn)

    with pytest.raises(ApplicationError) as exc_info:
        service.get_candidate("relationship", 999)

    assert exc_info.value.code is ErrorCode.CANDIDATE_NOT_FOUND
    assert exc_info.value.details == {"kind": "relationship", "candidate_id": 999}


def test_review_service_maps_invalid_kind_to_application_error() -> None:
    service = _service()

    with pytest.raises(ApplicationError) as exc_info:
        service.get_candidate("invalid", 10)

    assert exc_info.value.code is ErrorCode.CANDIDATE_INVALID_KIND
    assert exc_info.value.details == {"kind": "invalid"}


def test_review_service_maps_invalid_list_kind_to_application_error() -> None:
    service = _service()

    with pytest.raises(ApplicationError) as exc_info:
        service.list_candidates(ReviewCandidateFilters(kind="invalid", limit=50, offset=0))

    assert exc_info.value.code is ErrorCode.CANDIDATE_INVALID_KIND
    assert exc_info.value.details == {"kind": "invalid"}


def test_review_service_promotes_candidate_with_existing_promotion_service() -> None:
    captured_options: list[EncounterPromotionOptions] = []

    def promote_fn(
        session: Session,
        options: EncounterPromotionOptions,
    ) -> EncounterPromotionResult:
        captured_options.append(options)
        return EncounterPromotionResult(
            encounter_id=ENCOUNTER_ID,
            candidate_kind=options.candidate_kind,
            candidate_id=options.candidate_id,
            encounter_kind="direct_interaction",
            certainty_level="high",
            path_eligible=True,
            reused_existing=False,
        )

    service = _service(promote_candidate_fn=promote_fn)

    response = service.promote_candidate(
        "relationship",
        10,
        ReviewPromoteRequest(
            reviewed_by="lyl",
            evidence_summary="有明确见面证据",
            note="人工确认",
        ),
    )

    assert captured_options[0].candidate_kind is CandidateKind.RELATIONSHIP
    assert captured_options[0].evidence_summary == "有明确见面证据"
    assert captured_options[0].review_note == "人工确认"
    assert response.status == "promoted_to_encounter"
    assert response.encounter is not None
    assert response.encounter.encounter_id == ENCOUNTER_ID


def test_review_service_rejects_candidate_with_existing_status_service() -> None:
    def reject_fn(
        session: Session,
        kind: CandidateKind,
        candidate_id: int,
        *,
        reviewed_by: str,
        note: str,
    ) -> CandidateStatusChange:
        return CandidateStatusChange(
            candidate_kind=kind,
            candidate_id=candidate_id,
            review_status=CandidateReviewStatus.REJECTED,
            reviewed_by=reviewed_by,
            review_note=note,
        )

    service = _service(reject_candidate_fn=reject_fn)

    response = service.reject_candidate(
        "relationship",
        10,
        ReviewRejectRequest(reviewed_by="lyl", reason="证据不足"),
    )

    assert response.status == "rejected"
    assert response.reviewed_by == "lyl"
    assert response.encounter is None


def test_review_service_marks_candidate_needs_review_with_default_note() -> None:
    captured_note: list[str] = []

    def mark_fn(
        session: Session,
        kind: CandidateKind,
        candidate_id: int,
        *,
        reviewed_by: str,
        note: str,
    ) -> CandidateStatusChange:
        captured_note.append(note)
        return CandidateStatusChange(
            candidate_kind=kind,
            candidate_id=candidate_id,
            review_status=CandidateReviewStatus.NEEDS_REVIEW,
            reviewed_by=reviewed_by,
            review_note=note,
        )

    service = _service(mark_candidate_review_fn=mark_fn)

    response = service.mark_candidate_needs_review(
        "relationship",
        10,
        ReviewNeedsReviewRequest(reviewed_by="lyl"),
    )

    assert captured_note == ["needs review"]
    assert response.status == "needs_review"
    assert response.message == "needs review"


def test_review_service_maps_not_promotable_error() -> None:
    def promote_fn(
        session: Session,
        options: EncounterPromotionOptions,
    ) -> EncounterPromotionResult:
        raise EncounterOperationError("candidate requires --allow-non-default")

    service = _service(promote_candidate_fn=promote_fn)

    with pytest.raises(ApplicationError) as exc_info:
        service.promote_candidate(
            "relationship",
            10,
            ReviewPromoteRequest(
                reviewed_by="lyl",
                evidence_summary="证据摘要",
            ),
        )

    assert exc_info.value.code is ErrorCode.CANDIDATE_NOT_PROMOTABLE
    assert exc_info.value.details == {"kind": "relationship", "candidate_id": 10}


def test_review_service_maps_already_promoted_reject_error() -> None:
    def reject_fn(
        session: Session,
        kind: CandidateKind,
        candidate_id: int,
        *,
        reviewed_by: str,
        note: str,
    ) -> CandidateStatusChange:
        raise CandidateReviewError("candidate is already promoted; retract first")

    service = _service(reject_candidate_fn=reject_fn)

    with pytest.raises(ApplicationError) as exc_info:
        service.reject_candidate(
            "relationship",
            10,
            ReviewRejectRequest(reviewed_by="lyl", reason="证据不足"),
        )

    assert exc_info.value.code is ErrorCode.CANDIDATE_ALREADY_PROMOTED


def _service(**kwargs: object) -> ReviewService:
    kwargs.setdefault("list_ai_jobs_fn", _empty_ai_jobs)
    kwargs.setdefault("list_suggestions_fn", _empty_suggestions)
    return ReviewService(cast(Session, object()), **kwargs)  # type: ignore[arg-type]


def _empty_ai_jobs(
    session: Session,
    *,
    target_type: str,
    target_kind: str,
    target_id: int,
    limit: int,
) -> list[AIGenerationJobRecord]:
    return []


def _empty_suggestions(
    session: Session,
    filters: CandidateSuggestionListFilters,
) -> list[CandidateSuggestionRecord]:
    return []


def _summary(
    kind: CandidateKind,
    candidate_id: int,
    relation_label: str,
    *,
    strength: str = "high",
    basis: str = "direct_interaction_likely",
    person_a_id: UUID = PERSON_A_ID,
) -> CandidateSummary:
    return CandidateSummary(
        candidate_kind=kind,
        candidate_id=candidate_id,
        person_a_name="許幾",
        person_b_name="韓琦",
        cbdb_person_a_id=780,
        cbdb_person_b_id=630,
        candidate_strength=strength,
        candidate_basis=basis,
        relation_label=relation_label,
        source_work_id=1,
        pages="12a",
        review_status="unreviewed",
        person_a_id=person_a_id,
        person_b_id=PERSON_B_ID,
    )


def _detail(kind: CandidateKind, candidate_id: int) -> CandidateDetail:
    return CandidateDetail(
        candidate_kind=kind,
        candidate_id=candidate_id,
        person_a=_person(PERSON_A_ID, "許幾", 780),
        person_b=_person(PERSON_B_ID, "韓琦", 630),
        candidate_strength="high",
        candidate_basis="direct_interaction_likely",
        relation_label="同僚",
        source_work_id=1,
        pages="12a",
        notes="同在朝廷",
        review_status="promoted_to_encounter",
        reviewed_by="lyl",
        review_note="confirmed",
        promoted_encounter_id=ENCOUNTER_ID,
        source_name="assoc_data",
        source_table="assoc_data",
        source_pk="10",
        raw_cbdb_snapshot={},
        source_refs=[
            CandidateSourceRef(
                source_ref_id=100,
                source_work_id=1,
                title_zh="宋史",
                title_en=None,
                pages="12a",
                notes=None,
            )
        ],
        promotion_readiness=PromotionReadiness(
            default_promotable=True,
            default_path_eligible=True,
            reasons=[],
        ),
    )


def _person(person_id: UUID, name: str, cbdb_id: int) -> CandidatePerson:
    return CandidatePerson(
        person_id=person_id,
        cbdb_id=cbdb_id,
        primary_name_zh_hant=name,
        primary_name_zh_hans=None,
        primary_name_romanized=None,
        birth_year=None,
        death_year=None,
        external_ids=[str(cbdb_id)],
    )


def _job_record(*, status: str) -> AIGenerationJobRecord:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return AIGenerationJobRecord(
        id=UUID("00000000-0000-0000-0000-000000000501"),
        job_type="candidate_review_suggestion",
        target_type="candidate",
        target_kind="relationship",
        target_id=10,
        status=status,
        created_by="lyl",
        params={},
        result_ref_type="ai_candidate_review_suggestion",
        result_ref_id=UUID("00000000-0000-0000-0000-000000000601"),
        error_code=None,
        error_message=None,
        started_at=now,
        finished_at=now,
        queue_backend="database",
        queue_name=None,
        queue_job_id=None,
        enqueued_at=None,
        attempt_count=0,
        max_attempts=3,
        next_run_at=None,
        cancel_requested_at=None,
        worker_id=None,
        heartbeat_at=None,
        created_at=now,
        updated_at=now,
    )


def _suggestion_record() -> CandidateSuggestionRecord:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return CandidateSuggestionRecord(
        id=UUID("00000000-0000-0000-0000-000000000601"),
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=10,
        suggested_action="promote",
        priority_score=90,
        evidence_summary_draft="证据支持二人直接见面。",
        risk_flags=[],
        supporting_source_ref_ids=[100],
        review_questions=[],
        explanation="来源文本明确支持直接互动。",
        status="generated",
        reviewed_by=None,
        reviewed_at=None,
        review_note=None,
        created_at=now,
    )
