from dataclasses import dataclass
from typing import Any
from uuid import UUID

from figure_data.ai.candidate_repository import (
    CandidateSuggestionListFilters,
    NewCandidateReviewSuggestion,
    create_candidate_review_suggestion,
    get_candidate_review_suggestion,
    list_candidate_review_suggestions,
)
from figure_data.review.types import CandidateKind


@dataclass
class ScalarResult:
    value: object

    def scalar_one(self) -> object:
        return self.value


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> "MappingResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self.rows

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []
        self.suggestion_id = UUID("00000000-0000-0000-0000-000000000201")

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> object:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params or {})
        if "insert into figure_data.ai_candidate_review_suggestions" in sql:
            return ScalarResult(self.suggestion_id)
        row = {
            "id": self.suggestion_id,
            "ai_run_id": UUID("00000000-0000-0000-0000-000000000301"),
            "candidate_kind": "relationship",
            "candidate_id": 960698,
            "suggested_action": "needs_human_review",
            "priority_score": 70,
            "evidence_summary_draft": "结构化关系显示二人可能有互动。",
            "risk_flags": ["source_text_missing"],
            "supporting_source_ref_ids": [501],
            "review_questions": ["是否有原文？"],
            "explanation": "只基于输入材料。",
            "status": "generated",
            "reviewed_by": None,
            "reviewed_at": None,
            "review_note": None,
            "created_at": "2026-06-13T00:00:00+00:00",
        }
        return MappingResult([row])


def new_suggestion() -> NewCandidateReviewSuggestion:
    return NewCandidateReviewSuggestion(
        ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
        candidate_kind=CandidateKind.RELATIONSHIP,
        candidate_id=960698,
        suggested_action="needs_human_review",
        priority_score=70,
        evidence_summary_draft="结构化关系显示二人可能有互动。",
        risk_flags=["source_text_missing"],
        supporting_source_ref_ids=[501],
        review_questions=["是否有原文？"],
        explanation="只基于输入材料。",
    )


def test_create_candidate_review_suggestion_inserts_generated_record() -> None:
    session = FakeSession()

    suggestion_id = create_candidate_review_suggestion(
        session,  # type: ignore[arg-type]
        new_suggestion(),
    )

    assert suggestion_id == session.suggestion_id
    assert (
        "insert into figure_data.ai_candidate_review_suggestions"
        in session.statements[0]
    )
    assert session.params[0]["candidate_kind"] == "relationship"
    assert session.params[0]["status"] == "generated"


def test_list_candidate_review_suggestions_filters_status_and_kind() -> None:
    session = FakeSession()

    rows = list_candidate_review_suggestions(
        session,  # type: ignore[arg-type]
        CandidateSuggestionListFilters(
            status="generated",
            candidate_kind=CandidateKind.RELATIONSHIP,
            limit=10,
        ),
    )

    assert rows[0].candidate_id == 960698
    assert "where" in session.statements[0].lower()
    assert session.params[0]["status"] == "generated"
    assert session.params[0]["candidate_kind"] == "relationship"


def test_get_candidate_review_suggestion_loads_record() -> None:
    session = FakeSession()

    record = get_candidate_review_suggestion(
        session,  # type: ignore[arg-type]
        session.suggestion_id,
    )

    assert record.id == session.suggestion_id
    assert record.ai_run_id == UUID("00000000-0000-0000-0000-000000000301")
    assert record.risk_flags == ["source_text_missing"]
