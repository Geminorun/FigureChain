from uuid import UUID

from figure_data.ai.candidate_context import candidate_review_prompt_input_from_detail
from figure_data.review.types import (
    CandidateDetail,
    CandidateKind,
    CandidatePerson,
    CandidateSourceRef,
    PromotionReadiness,
)


def candidate_person(name: str, person_id: str, cbdb_id: int) -> CandidatePerson:
    return CandidatePerson(
        person_id=UUID(person_id),
        cbdb_id=cbdb_id,
        primary_name_zh_hant=name,
        primary_name_zh_hans=name,
        primary_name_romanized=None,
        birth_year=1000,
        death_year=1060,
        external_ids=[f"cbdb:{cbdb_id}"],
    )


def candidate_detail() -> CandidateDetail:
    return CandidateDetail(
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        person_a=candidate_person("许几", "00000000-0000-0000-0000-000000000101", 101),
        person_b=candidate_person("韩琦", "00000000-0000-0000-0000-000000000102", 102),
        candidate_strength="high",
        candidate_basis="direct_interaction_likely",
        relation_label="谒见",
        source_work_id=123,
        pages="卷一",
        notes="许几谒韩琦于魏",
        review_status="unreviewed",
        reviewed_by=None,
        review_note=None,
        promoted_encounter_id=None,
        source_name="cbdb",
        source_table="ASSOC_DATA",
        source_pk="960698",
        raw_cbdb_snapshot={"source_table": "ASSOC_DATA", "source_pk": "960698"},
        source_refs=[
            CandidateSourceRef(
                source_ref_id=501,
                source_work_id=123,
                title_zh="宋史",
                title_en=None,
                pages="卷一",
                notes="许几谒韩琦于魏",
            )
        ],
        promotion_readiness=PromotionReadiness(
            default_promotable=True,
            default_path_eligible=True,
            reasons=[],
        ),
    )


def test_candidate_review_prompt_input_preserves_traceable_fields() -> None:
    prompt_input = candidate_review_prompt_input_from_detail(
        candidate_detail(),
        has_active_path_encounter_for_pair=False,
    )
    payload = prompt_input.model_dump(mode="json")

    assert payload["candidate"]["kind"] == "relationship"
    assert payload["candidate"]["id"] == 960698
    assert payload["candidate"]["candidate_strength"] == "high"
    assert payload["candidate"]["candidate_basis"] == "direct_interaction_likely"
    assert payload["candidate"]["review_status"] == "unreviewed"
    assert payload["candidate"]["promotion_readiness"]["default_promotable"] is True
    assert payload["candidate"]["has_active_path_encounter_for_pair"] is False
    assert payload["person_a"]["primary_name_zh_hant"] == "许几"
    assert payload["person_b"]["primary_name_zh_hant"] == "韩琦"
    assert payload["source_refs"][0]["source_ref_id"] == 501


def test_candidate_review_prompt_input_marks_existing_path_encounter() -> None:
    prompt_input = candidate_review_prompt_input_from_detail(
        candidate_detail(),
        has_active_path_encounter_for_pair=True,
    )

    assert prompt_input.candidate.has_active_path_encounter_for_pair is True
