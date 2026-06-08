from typing import Any
from uuid import UUID

from pytest import MonkeyPatch, raises

from figure_data.db.enums import CertaintyLevel, EncounterKind
from figure_data.encounters.promotion import promote_candidate_to_encounter
from figure_data.encounters.types import EncounterOperationError, EncounterPromotionOptions
from figure_data.review.types import (
    CandidateDetail,
    CandidateKind,
    CandidatePerson,
    CandidateSourceRef,
    PromotionReadiness,
)


class FakeScalarResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> FakeScalarResult:
        self.statements.append(str(statement))
        self.params.append(params)
        if "insert into figure_data.encounter_evidence" in str(statement):
            return FakeScalarResult(1)
        if "select e.id" in str(statement):
            return FakeScalarResult(None)
        return FakeScalarResult(None)


def candidate_detail() -> CandidateDetail:
    person_a = CandidatePerson(
        person_id=UUID("00000000-0000-0000-0000-000000000001"),
        cbdb_id=25403,
        primary_name_zh_hant="諸葛亮",
        primary_name_zh_hans="诸葛亮",
        primary_name_romanized="Zhuge Liang",
        birth_year=181,
        death_year=234,
        external_ids=["25403"],
    )
    person_b = CandidatePerson(
        person_id=UUID("00000000-0000-0000-0000-000000000002"),
        cbdb_id=21204,
        primary_name_zh_hant="司馬懿",
        primary_name_zh_hans="司马懿",
        primary_name_romanized="Sima Yi",
        birth_year=179,
        death_year=251,
        external_ids=["21204"],
    )
    return CandidateDetail(
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=123,
        person_a=person_a,
        person_b=person_b,
        candidate_strength="high",
        candidate_basis="direct_interaction_likely",
        relation_label="敵對",
        source_work_id=1,
        pages="12a",
        notes="sample note",
        review_status="unreviewed",
        reviewed_by=None,
        review_note=None,
        promoted_encounter_id=None,
        source_name="cbdb",
        source_table="ASSOC_DATA",
        source_pk="_rowid=1",
        raw_cbdb_snapshot={"source_table": "ASSOC_DATA", "source_pk": "_rowid=1"},
        source_refs=[
            CandidateSourceRef(
                source_ref_id=77,
                source_work_id=1,
                title_zh="三國志",
                title_en=None,
                pages="12a",
                notes="source note",
            )
        ],
        promotion_readiness=PromotionReadiness(
            default_promotable=True,
            default_path_eligible=True,
            reasons=[],
        ),
    )


def test_promote_default_candidate_creates_encounter_evidence_and_candidate_link(
    monkeypatch: MonkeyPatch,
) -> None:
    session = FakeSession()

    import figure_data.encounters.promotion as promotion_module

    monkeypatch.setattr(
        promotion_module,
        "get_candidate_detail",
        lambda session, kind, candidate_id: candidate_detail(),
    )

    result = promote_candidate_to_encounter(
        session,  # type: ignore[arg-type]
        EncounterPromotionOptions(
            candidate_kind=CandidateKind.RELATIONSHIP,
            candidate_id=123,
            reviewed_by="lyl",
            evidence_summary="CBDB 关系代码显示两人有直接互动",
        ),
    )

    joined_sql = "\n".join(session.statements)
    assert result.path_eligible is True
    assert "insert into figure_data.encounters" in joined_sql
    assert "insert into figure_data.encounter_evidence" in joined_sql
    assert "review_status = :review_status" in joined_sql
    assert "promoted_encounter_id = :encounter_id" in joined_sql


def test_promote_non_default_candidate_requires_explicit_allow(
    monkeypatch: MonkeyPatch,
) -> None:
    detail = candidate_detail()
    non_default = CandidateDetail(
        **{
            **detail.__dict__,
            "candidate_strength": "medium",
            "promotion_readiness": PromotionReadiness(
                default_promotable=False,
                default_path_eligible=False,
                reasons=["strength_is_not_high"],
            ),
        }
    )

    import figure_data.encounters.promotion as promotion_module

    monkeypatch.setattr(
        promotion_module,
        "get_candidate_detail",
        lambda session, kind, candidate_id: non_default,
    )

    with raises(EncounterOperationError, match="requires --allow-non-default"):
        promote_candidate_to_encounter(
            FakeSession(),  # type: ignore[arg-type]
            EncounterPromotionOptions(
                candidate_kind=CandidateKind.RELATIONSHIP,
                candidate_id=123,
                reviewed_by="lyl",
                evidence_summary="同场共事，保留解释",
            ),
        )


def test_promote_refuses_candidate_without_people(monkeypatch: MonkeyPatch) -> None:
    detail = candidate_detail()
    person_without_id = CandidatePerson(
        person_id=None,
        cbdb_id=None,
        primary_name_zh_hant=None,
        primary_name_zh_hans=None,
        primary_name_romanized=None,
        birth_year=None,
        death_year=None,
        external_ids=[],
    )
    invalid = CandidateDetail(**{**detail.__dict__, "person_a": person_without_id})

    import figure_data.encounters.promotion as promotion_module

    monkeypatch.setattr(
        promotion_module,
        "get_candidate_detail",
        lambda session, kind, candidate_id: invalid,
    )

    with raises(EncounterOperationError, match="candidate is missing person ids"):
        promote_candidate_to_encounter(
            FakeSession(),  # type: ignore[arg-type]
            EncounterPromotionOptions(
                candidate_kind=CandidateKind.RELATIONSHIP,
                candidate_id=123,
                reviewed_by="lyl",
                evidence_summary="证据",
            ),
        )


def test_promote_refuses_default_path_edge_with_medium_certainty(
    monkeypatch: MonkeyPatch,
) -> None:
    import figure_data.encounters.promotion as promotion_module

    monkeypatch.setattr(
        promotion_module,
        "get_candidate_detail",
        lambda session, kind, candidate_id: candidate_detail(),
    )

    with raises(EncounterOperationError, match="path_eligible requires high certainty"):
        promote_candidate_to_encounter(
            FakeSession(),  # type: ignore[arg-type]
            EncounterPromotionOptions(
                candidate_kind=CandidateKind.RELATIONSHIP,
                candidate_id=123,
                reviewed_by="lyl",
                evidence_summary="证据",
                certainty_level=CertaintyLevel.MEDIUM,
            ),
        )


def test_promote_refuses_path_edge_for_non_direct_encounter_kind(
    monkeypatch: MonkeyPatch,
) -> None:
    import figure_data.encounters.promotion as promotion_module

    monkeypatch.setattr(
        promotion_module,
        "get_candidate_detail",
        lambda session, kind, candidate_id: candidate_detail(),
    )

    with raises(EncounterOperationError, match="path_eligible requires direct_interaction"):
        promote_candidate_to_encounter(
            FakeSession(),  # type: ignore[arg-type]
            EncounterPromotionOptions(
                candidate_kind=CandidateKind.RELATIONSHIP,
                candidate_id=123,
                reviewed_by="lyl",
                evidence_summary="证据",
                encounter_kind=EncounterKind.CO_PRESENCE,
            ),
        )
