from datetime import UTC, datetime
from uuid import UUID

from pytest import raises

from figure_data.ai.chain_context import (
    InvalidChainContextError,
    build_chain_explanation_prompt_input,
)
from figure_data.encounters.types import EncounterDetail, EncounterEvidenceDetail
from figure_data.graph.types import ChainEdge, ChainLookupResult, ChainPath, ChainPerson
from figure_data.review.types import CandidatePerson, CandidateSourceRef

ENCOUNTER_ID = "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"
SOURCE_PERSON_ID = "38966b03-8aa7-5143-8021-2d266889b6c5"
TARGET_PERSON_ID = "46cfdf66-08c4-5876-964b-4a95d098afe9"
_DEFAULT_PATH = object()


def chain_result(*, path: ChainPath | None | object = _DEFAULT_PATH) -> ChainLookupResult:
    resolved_path = (
        ChainPath(
            people=(
                ChainPerson(
                    person_id=SOURCE_PERSON_ID,
                    display_name="許幾",
                    birth_year=1054,
                    death_year=1115,
                    cbdb_external_id="780",
                ),
                ChainPerson(
                    person_id=TARGET_PERSON_ID,
                    display_name="韓琦",
                    birth_year=1008,
                    death_year=1075,
                    cbdb_external_id="630",
                ),
            ),
            edges=(
                ChainEdge(
                    encounter_id=ENCOUNTER_ID,
                    encounter_kind="direct_interaction",
                    certainty_level="high",
                    pages="11905",
                    evidence_summary="许几谒韩琦于魏",
                ),
            ),
        )
        if not isinstance(path, ChainPath) and path is not None
        else path
    )
    return ChainLookupResult(
        source_person_id=SOURCE_PERSON_ID,
        target_person_id=TARGET_PERSON_ID,
        max_depth=12,
        path=resolved_path,
    )


def encounter_detail(*, evidence: list[EncounterEvidenceDetail] | None = None) -> EncounterDetail:
    now = datetime(2026, 6, 13, tzinfo=UTC)
    return EncounterDetail(
        encounter_id=UUID(ENCOUNTER_ID),
        person_a=CandidatePerson(
            person_id=UUID(SOURCE_PERSON_ID),
            cbdb_id=780,
            primary_name_zh_hant="許幾",
            primary_name_zh_hans="许几",
            primary_name_romanized="Xu Ji",
            birth_year=1054,
            death_year=1115,
            external_ids=["780"],
        ),
        person_b=CandidatePerson(
            person_id=UUID(TARGET_PERSON_ID),
            cbdb_id=630,
            primary_name_zh_hant="韓琦",
            primary_name_zh_hans="韩琦",
            primary_name_romanized="Han Qi",
            birth_year=1008,
            death_year=1075,
            external_ids=["630"],
        ),
        encounter_kind="direct_interaction",
        certainty_level="high",
        path_eligible=True,
        source_work_id=7596,
        pages="11905",
        evidence_summary="许几谒韩琦于魏",
        review_note=None,
        status="active",
        reviewed_by="lyl",
        reviewed_at=now,
        created_at=now,
        updated_at=now,
        evidence=evidence
        if evidence is not None
        else [
            EncounterEvidenceDetail(
                evidence_id=12,
                candidate_table="relationship_candidates",
                candidate_id=960664,
                source_ref_id=3853784,
                source_work_id=7596,
                pages="11905",
                evidence_kind="candidate",
                evidence_summary="许几谒韩琦于魏",
                created_at=now,
            )
        ],
        source_refs=[
            CandidateSourceRef(
                source_ref_id=3853784,
                source_work_id=7596,
                title_zh=None,
                title_en=None,
                pages="11905",
                notes="以诸生谒韩琦于魏",
            )
        ],
    )


def test_build_chain_explanation_prompt_input_uses_only_reviewed_context() -> None:
    prompt_input = build_chain_explanation_prompt_input(
        result=chain_result(),
        encounter_details={ENCOUNTER_ID: encounter_detail()},
        language="zh-Hans",
    )
    payload = prompt_input.model_dump(mode="json")

    assert payload["source_person_id"] == SOURCE_PERSON_ID
    assert payload["target_person_id"] == TARGET_PERSON_ID
    assert payload["people"][0]["display_name"] == "許幾"
    assert payload["encounters"][0]["encounter_id"] == ENCOUNTER_ID
    assert payload["encounters"][0]["source_refs"][0]["source_ref_id"] == 3853784


def test_build_chain_explanation_prompt_input_rejects_no_path() -> None:
    with raises(InvalidChainContextError, match="found path"):
        build_chain_explanation_prompt_input(
            result=chain_result(path=None),
            encounter_details={},
            language="zh-Hans",
        )


def test_build_chain_explanation_prompt_input_rejects_missing_evidence() -> None:
    with raises(InvalidChainContextError, match="missing encounter evidence"):
        build_chain_explanation_prompt_input(
            result=chain_result(),
            encounter_details={ENCOUNTER_ID: encounter_detail(evidence=[])},
            language="zh-Hans",
        )
