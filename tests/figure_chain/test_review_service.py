from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.services.review import ReviewCandidateFilters, ReviewService
from figure_data.review.candidate_listing import CandidateListFilters
from figure_data.review.types import (
    CandidateDetail,
    CandidateKind,
    CandidatePerson,
    CandidateReviewError,
    CandidateSourceRef,
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

    service = ReviewService(cast(Session, object()), list_summaries_fn=list_fn)

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
    def list_fn(session: Session, filters: CandidateListFilters) -> list[CandidateSummary]:
        return [
            _summary(CandidateKind.RELATIONSHIP, 10, "同僚", strength="high"),
            _summary(
                CandidateKind.RELATIONSHIP,
                11,
                "同僚",
                strength="low",
                person_a_id=UUID("00000000-0000-0000-0000-000000000099"),
            ),
        ]

    service = ReviewService(cast(Session, object()), list_summaries_fn=list_fn)

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


def test_review_service_applies_offset_after_filters() -> None:
    def list_fn(session: Session, filters: CandidateListFilters) -> list[CandidateSummary]:
        return [
            _summary(CandidateKind.RELATIONSHIP, 10, "同僚"),
            _summary(CandidateKind.RELATIONSHIP, 11, "同僚"),
        ]

    service = ReviewService(cast(Session, object()), list_summaries_fn=list_fn)

    response = service.list_candidates(ReviewCandidateFilters(limit=1, offset=1))

    assert response.count == 1
    assert response.items[0].candidate_id == 11


def test_review_service_returns_empty_list() -> None:
    service = ReviewService(
        cast(Session, object()),
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

    service = ReviewService(cast(Session, object()), get_detail_fn=detail_fn)

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


def test_review_service_maps_missing_candidate_to_application_error() -> None:
    def detail_fn(session: Session, kind: CandidateKind, candidate_id: int) -> CandidateDetail:
        raise CandidateReviewError("candidate not found")

    service = ReviewService(cast(Session, object()), get_detail_fn=detail_fn)

    with pytest.raises(ApplicationError) as exc_info:
        service.get_candidate("relationship", 999)

    assert exc_info.value.code is ErrorCode.CANDIDATE_NOT_FOUND
    assert exc_info.value.details == {"kind": "relationship", "candidate_id": 999}


def test_review_service_maps_invalid_kind_to_application_error() -> None:
    service = ReviewService(cast(Session, object()))

    with pytest.raises(ApplicationError) as exc_info:
        service.get_candidate("invalid", 10)

    assert exc_info.value.code is ErrorCode.CANDIDATE_INVALID_KIND
    assert exc_info.value.details == {"kind": "invalid"}


def test_review_service_maps_invalid_list_kind_to_application_error() -> None:
    service = ReviewService(cast(Session, object()))

    with pytest.raises(ApplicationError) as exc_info:
        service.list_candidates(ReviewCandidateFilters(kind="invalid", limit=50, offset=0))

    assert exc_info.value.code is ErrorCode.CANDIDATE_INVALID_KIND
    assert exc_info.value.details == {"kind": "invalid"}


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
