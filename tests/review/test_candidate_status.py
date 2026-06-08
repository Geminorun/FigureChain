from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

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
    def __init__(
        self,
        row: dict[str, Any] | None = None,
        *,
        encounter_row: dict[str, Any] | None = None,
    ) -> None:
        self.row = row
        self.encounter_row = encounter_row
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        if "from figure_data.encounters" in str(statement):
            return MappingResult(self.encounter_row)
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


def test_reject_candidate_allows_retracted_historical_encounter_link() -> None:
    encounter_id = UUID("00000000-0000-0000-0000-000000000001")
    session = FakeSession(
        {
            "review_status": "needs_review",
            "promoted_encounter_id": encounter_id,
        },
        encounter_row={"status": "retracted"},
    )

    change = reject_candidate(
        session,  # type: ignore[arg-type]
        CandidateKind.RELATIONSHIP,
        123,
        reviewed_by="lyl",
        note="撤回后人工复核为无效",
    )

    assert change.review_status.value == "rejected"
    assert "from figure_data.encounters" in "\n".join(session.statements)
    assert "promoted_encounter_id =" not in session.statements[-1]


def test_reject_candidate_refuses_active_historical_encounter_link() -> None:
    encounter_id = UUID("00000000-0000-0000-0000-000000000001")
    session = FakeSession(
        {
            "review_status": "needs_review",
            "promoted_encounter_id": encounter_id,
        },
        encounter_row={"status": "active"},
    )

    with raises(CandidateReviewError, match="candidate is linked to an active encounter"):
        reject_candidate(
            session,  # type: ignore[arg-type]
            CandidateKind.RELATIONSHIP,
            123,
            reviewed_by="lyl",
            note="证据不足",
        )
