from dataclasses import dataclass
from typing import Any

from figure_data.review.candidate_listing import CandidateListFilters, list_candidate_summaries
from figure_data.review.types import CandidateKind


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> "MappingResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return MappingResult(
            [
                {
                    "candidate_kind": "relationship",
                    "candidate_id": 123,
                    "person_a_name": "諸葛亮",
                    "person_b_name": "司馬懿",
                    "cbdb_person_a_id": 25403,
                    "cbdb_person_b_id": 21204,
                    "candidate_strength": "high",
                    "candidate_basis": "direct_interaction_likely",
                    "relation_label": "敵對",
                    "source_work_id": 1,
                    "pages": "12a",
                    "review_status": "unreviewed",
                }
            ]
        )


def test_list_candidate_summaries_builds_relationship_query() -> None:
    session = FakeSession()

    results = list_candidate_summaries(
        session,  # type: ignore[arg-type]
        CandidateListFilters(kind=CandidateKind.RELATIONSHIP, limit=5),
    )

    assert len(results) == 1
    assert results[0].candidate_kind is CandidateKind.RELATIONSHIP
    assert "figure_data.relationship_candidates" in session.statements[0]
    assert "figure_data.kinship_candidates" not in session.statements[0]
    assert session.params[0]["limit"] == 5


def test_list_candidate_summaries_builds_union_when_kind_is_not_supplied() -> None:
    session = FakeSession()

    list_candidate_summaries(session, CandidateListFilters(limit=5))  # type: ignore[arg-type]

    assert "union all" in session.statements[0].lower()
    assert "figure_data.relationship_candidates" in session.statements[0]
    assert "figure_data.kinship_candidates" in session.statements[0]


def test_list_candidate_summaries_adds_filters() -> None:
    session = FakeSession()

    list_candidate_summaries(
        session,  # type: ignore[arg-type]
        CandidateListFilters(
            kind=CandidateKind.KINSHIP,
            review_status="needs_review",
            strength="medium",
            basis="family_close",
            limit=10,
        ),
    )

    statement = session.statements[0]
    assert "candidate_strength = :strength" in statement
    assert "candidate_basis = :basis" in statement
    assert "review_status = :review_status" in statement
    assert session.params[0]["strength"] == "medium"
    assert session.params[0]["basis"] == "family_close"
    assert session.params[0]["review_status"] == "needs_review"
