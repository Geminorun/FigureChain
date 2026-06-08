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
    session = FakeSession([0, 0, 0, 0, 0, 0])

    checks = validate_encounters(session)  # type: ignore[arg-type]

    assert all(check.passed for check in checks)
    assert {check.name for check in checks} == {
        "encounters:no_self_loops",
        "encounters:active_have_evidence",
        "encounters:retracted_not_path_eligible",
        "encounters:path_eligible_certainty",
        "encounters:relationship_promotions_resolve",
        "encounters:kinship_promotions_resolve",
    }


def test_validate_encounters_reports_failing_counts() -> None:
    session = FakeSession([1, 2, 3, 4, 5, 6])

    checks = validate_encounters(session)  # type: ignore[arg-type]

    assert not all(check.passed for check in checks)
    assert checks[0].detail == "violations=1"
    assert checks[-1].detail == "violations=6"
