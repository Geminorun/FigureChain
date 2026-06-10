from dataclasses import dataclass
from typing import Any

from figure_data.expansion.candidate_planning import (
    ExpansionCandidateFilters,
    plan_encounter_expansion,
)


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
                    "candidate_id": 960664,
                    "person_a_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
                    "person_b_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
                    "person_a_name": "許幾",
                    "person_b_name": "韓琦",
                    "cbdb_person_a_id": 780,
                    "cbdb_person_b_id": 630,
                    "candidate_strength": "high",
                    "candidate_basis": "direct_interaction_likely",
                    "relation_label": "谒",
                    "source_work_id": 7596,
                    "source_ref_id": 3853784,
                    "pages": "11905",
                    "review_status": "unreviewed",
                    "active_path_neighbors": 1,
                    "score": 135,
                }
            ]
        )


def test_plan_encounter_expansion_uses_stage_three_filters() -> None:
    session = FakeSession()

    rows = plan_encounter_expansion(
        session,  # type: ignore[arg-type]
        ExpansionCandidateFilters(limit=25),
    )

    assert rows[0].candidate_id == 960664
    assert rows[0].score == 135
    statement = session.statements[0]
    assert "from figure_data.relationship_candidates rc" in statement
    assert "rc.candidate_strength = 'high'" in statement
    assert "rc.candidate_basis = 'direct_interaction_likely'" in statement
    assert "rc.person_a_id is not null" in statement
    assert "rc.person_b_id is not null" in statement
    assert "rc.person_a_id <> rc.person_b_id" in statement
    assert "from figure_data.source_refs sr" in statement
    assert "sr.ref_source_table = rc.source_table" in statement
    assert "sr.ref_source_pk = rc.source_pk" in statement
    assert "),\n                ranked_candidates as (" in statement
    assert "null::integer as source_ref_id" not in statement
    assert "left join figure_data.encounters existing_path" in statement
    assert "existing_path.id is null" in statement
    assert "figure_data.kinship_candidates" not in statement
    assert "limit :limit" in statement
    params = session.params[0]
    assert params is not None
    assert params["limit"] == 25


def test_plan_encounter_expansion_accepts_review_status_filter() -> None:
    session = FakeSession()

    plan_encounter_expansion(
        session,  # type: ignore[arg-type]
        ExpansionCandidateFilters(review_status="needs_review", limit=10),
    )

    assert "rc.review_status = :review_status" in session.statements[0]
    params = session.params[0]
    assert params is not None
    assert params["review_status"] == "needs_review"
