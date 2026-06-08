from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from figure_data.encounters.validation import validate_encounters


@dataclass
class ScalarResult:
    value: int

    def scalar_one(self) -> int:
        return self.value


class FakeSession:
    def __init__(self, counts: Iterable[int]) -> None:
        self.counts = list(counts)
        self.statements: list[str] = []

    def execute(self, statement: Any) -> ScalarResult:
        self.statements.append(str(statement))
        return ScalarResult(self.counts.pop(0))


def test_validate_encounters_returns_passing_checks_when_counts_are_zero() -> None:
    session = FakeSession([0, 0, 0, 0, 0, 0, 0, 0])

    checks = validate_encounters(session)  # type: ignore[arg-type]

    assert all(check.passed for check in checks)
    assert {check.name for check in checks} == {
        "encounters:no_self_loops",
        "encounters:active_have_evidence",
        "encounters:retracted_not_path_eligible",
        "encounters:path_eligible_certainty",
        "encounters:path_eligible_kind",
        "encounters:relationship_promotions_resolve",
        "encounters:kinship_promotions_resolve",
        "encounters:candidates_single_active_encounter",
    }


def test_validate_encounters_reports_failing_counts() -> None:
    session = FakeSession([1, 2, 3, 4, 5, 6, 7, 8])

    checks = validate_encounters(session)  # type: ignore[arg-type]

    assert not all(check.passed for check in checks)
    assert checks[0].detail == "violations=1"
    assert checks[-1].detail == "violations=8"


def test_validate_encounters_checks_duplicate_active_candidate_links() -> None:
    session = FakeSession([0, 0, 0, 0, 0, 0, 0, 0])

    validate_encounters(session)  # type: ignore[arg-type]

    assert "candidate_table" in session.statements[-1]
    assert "having count(distinct e.id) > 1" in session.statements[-1]


def test_validate_encounters_rejects_all_non_high_path_edges() -> None:
    session = FakeSession([0, 0, 0, 0, 0, 0, 0, 0])

    validate_encounters(session)  # type: ignore[arg-type]

    certainty_sql = session.statements[3]
    assert "path_eligible = true" in certainty_sql
    assert "certainty_level <> 'high'" in certainty_sql
    assert "review_note" not in certainty_sql


def test_validate_encounters_rejects_non_direct_path_edges() -> None:
    session = FakeSession([0, 0, 0, 0, 0, 0, 0, 0])

    validate_encounters(session)  # type: ignore[arg-type]

    kind_sql = session.statements[4]
    assert "path_eligible = true" in kind_sql
    assert "encounter_kind <> 'direct_interaction'" in kind_sql
