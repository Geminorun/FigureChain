from uuid import UUID

from figure_chain.schemas import (
    ReviewActionResponse,
    ReviewAiJobSummary,
    ReviewCandidateDetailResponse,
    ReviewCandidateListResponse,
    ReviewCandidatePersonResponse,
    ReviewCandidateRelationResponse,
    ReviewCandidateSummary,
    ReviewLinkedEncounterResponse,
    ReviewNeedsReviewRequest,
    ReviewPromoteRequest,
    ReviewPromotionReadinessResponse,
    ReviewRejectRequest,
)


def test_review_candidate_list_schema_has_stable_summary_fields() -> None:
    readiness = ReviewPromotionReadinessResponse(
        default_promotable=True,
        default_path_eligible=True,
        reasons=[],
    )
    person = ReviewCandidatePersonResponse(
        person_id="00000000-0000-0000-0000-000000000001",
        cbdb_id=780,
        display_name="許幾",
        primary_name_zh_hant="許幾",
        primary_name_zh_hans="许几",
        primary_name_romanized="Xu Ji",
        birth_year=None,
        death_year=None,
    )

    response = ReviewCandidateListResponse(
        items=[
            ReviewCandidateSummary(
                kind="relationship",
                candidate_id=1,
                person_a=person,
                person_b=person,
                relation_type="associate",
                time_summary="1040",
                place_summary=None,
                status="needs_review",
                confidence=0.9,
                evidence_count=2,
                source_count=1,
                promotion_readiness=readiness,
                latest_ai_job_status=None,
                has_ai_suggestion=False,
            )
        ],
        limit=50,
        offset=0,
        count=1,
    )

    payload = response.model_dump()

    assert payload["items"][0]["kind"] == "relationship"
    assert payload["items"][0]["promotion_readiness"]["default_promotable"] is True
    assert payload["items"][0]["latest_ai_job_status"] is None


def test_review_candidate_detail_schema_keeps_ai_fields_stable_when_empty() -> None:
    person = ReviewCandidatePersonResponse(
        person_id="00000000-0000-0000-0000-000000000001",
        cbdb_id=780,
        display_name="許幾",
        primary_name_zh_hant="許幾",
        primary_name_zh_hans="许几",
        primary_name_romanized="Xu Ji",
        birth_year=None,
        death_year=None,
    )

    response = ReviewCandidateDetailResponse(
        kind="relationship",
        candidate_id=1,
        person_a=person,
        person_b=person,
        relation=ReviewCandidateRelationResponse(
            relation_type="associate",
            basis="direct",
            strength="high",
            notes=None,
            source_name="宋史",
            source_table="assoc_data",
            source_pk="1",
        ),
        time=None,
        place=None,
        status="needs_review",
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
        ai_jobs=[
            ReviewAiJobSummary(
                run_id=UUID("00000000-0000-0000-0000-000000000010"),
                status="succeeded",
                purpose="candidate_review_suggestion",
                created_at=None,
                finished_at=None,
            )
        ],
    )

    payload = response.model_dump()

    assert payload["latest_ai_suggestion"] is None
    assert payload["ai_jobs"][0]["status"] == "succeeded"


def test_review_action_request_schemas_have_required_fields_and_defaults() -> None:
    promote = ReviewPromoteRequest(
        reviewed_by="lyl",
        evidence_summary="有明确见面证据",
    )
    reject = ReviewRejectRequest(reviewed_by="lyl", reason="证据不足")
    needs_review = ReviewNeedsReviewRequest(reviewed_by="lyl")

    assert promote.allow_non_default is False
    assert promote.note is None
    assert reject.reason == "证据不足"
    assert needs_review.note is None


def test_review_action_response_schema_carries_candidate_and_encounter_state() -> None:
    response = ReviewActionResponse(
        kind="relationship",
        candidate_id=10,
        status="promoted_to_encounter",
        reviewed_by="lyl",
        encounter=ReviewLinkedEncounterResponse(
            encounter_id=UUID("00000000-0000-0000-0000-000000000003"),
            status="active",
        ),
        message=None,
    )

    payload = response.model_dump()

    assert payload["status"] == "promoted_to_encounter"
    assert payload["encounter"]["status"] == "active"
