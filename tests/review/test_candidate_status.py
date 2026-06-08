from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pytest import raises

from figure_data.review.candidate_status import mark_candidate_for_review, reject_candidate
from figure_data.review.types import CandidateKind, CandidateReviewError


@dataclass
class MappingResult:
    row: dict[str, Any] | None

    def mappings(self) -> "MappingResult":
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self.row


class FakeSession:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self.row = row
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return MappingResult(self.row)


def test_reject_candidate_updates_only_review_fields() -> None:
    session = FakeSession({"review_status": "unreviewed", "promoted_encounter_id": None})

    change = reject_candidate(
        session,  # type: ignore[arg-type]
        CandidateKind.RELATIONSHIP,
        123,
        reviewed_by="lyl",
        note="书信关系不能证明见面",
    )

    assert change.review_status.value == "rejected"
    assert "promoted_encounter_id =" not in session.statements[-1]
    params = session.params[-1]
    assert params is not None
    assert params["reviewed_by"] == "lyl"
    assert params["review_note"] == "书信关系不能证明见面"


def test_mark_candidate_for_review_requires_note() -> None:
    session = FakeSession({"review_status": "unreviewed", "promoted_encounter_id": None})

    with raises(CandidateReviewError, match="review_note is required"):
        mark_candidate_for_review(
            session,  # type: ignore[arg-type]
            CandidateKind.KINSHIP,
            123,
            reviewed_by="lyl",
            note=" ",
        )


def test_reject_candidate_refuses_promoted_candidates() -> None:
    session = FakeSession(
        {
            "review_status": "promoted_to_encounter",
            "promoted_encounter_id": uuid4(),
        }
    )

    with raises(CandidateReviewError, match="candidate is already promoted"):
        reject_candidate(
            session,  # type: ignore[arg-type]
            CandidateKind.RELATIONSHIP,
            123,
            reviewed_by="lyl",
            note="证据不足",
        )
