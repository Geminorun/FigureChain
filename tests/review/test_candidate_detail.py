from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.review.candidate_detail import get_candidate_detail
from figure_data.review.types import CandidateKind, CandidateReviewError


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> "MappingResult":
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class FakeSession:
    def __init__(
        self,
        candidate_rows: list[dict[str, Any]],
        source_rows: list[dict[str, Any]],
    ) -> None:
        self.candidate_rows = candidate_rows
        self.source_rows = source_rows
        self.statements: list[str] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        if "figure_data.source_refs" in str(statement):
            return MappingResult(self.source_rows)
        return MappingResult(self.candidate_rows)


def candidate_row() -> dict[str, Any]:
    person_a_id = UUID("00000000-0000-0000-0000-000000000001")
    person_b_id = UUID("00000000-0000-0000-0000-000000000002")
    return {
        "candidate_id": 123,
        "person_a_id": person_a_id,
        "person_b_id": person_b_id,
        "person_a_cbdb_id": 25403,
        "person_b_cbdb_id": 21204,
        "person_a_name_hant": "諸葛亮",
        "person_a_name_hans": "诸葛亮",
        "person_a_name_romanized": "Zhuge Liang",
        "person_a_birth_year": 181,
        "person_a_death_year": 234,
        "person_a_external_ids": ["25403"],
        "person_b_name_hant": "司馬懿",
        "person_b_name_hans": "司马懿",
        "person_b_name_romanized": "Sima Yi",
        "person_b_birth_year": 179,
        "person_b_death_year": 251,
        "person_b_external_ids": ["21204"],
        "candidate_strength": "high",
        "candidate_basis": "direct_interaction_likely",
        "relation_label": "敵對",
        "source_work_id": 1,
        "pages": "12a",
        "notes": "sample note",
        "review_status": "unreviewed",
        "reviewed_by": None,
        "review_note": None,
        "promoted_encounter_id": None,
        "source_name": "cbdb",
        "source_table": "ASSOC_DATA",
        "source_pk": "123",
    }


def test_get_candidate_detail_returns_people_sources_and_readiness() -> None:
    session = FakeSession(
        [candidate_row()],
        [
            {
                "source_ref_id": 77,
                "source_work_id": 1,
                "title_zh": "三國志",
                "title_en": "Records of the Three Kingdoms",
                "pages": "12a",
                "notes": "source note",
            }
        ],
    )

    detail = get_candidate_detail(
        session,  # type: ignore[arg-type]
        CandidateKind.RELATIONSHIP,
        123,
    )

    assert detail.person_a.primary_name_zh_hant == "諸葛亮"
    assert detail.source_refs[0].title_zh == "三國志"
    assert detail.promotion_readiness.default_promotable is True
    assert detail.promotion_readiness.default_path_eligible is True


def test_get_candidate_detail_raises_for_missing_candidate() -> None:
    session = FakeSession([], [])

    with raises(CandidateReviewError, match="candidate not found"):
        get_candidate_detail(session, CandidateKind.RELATIONSHIP, 404)  # type: ignore[arg-type]
