from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.encounters.query import EncounterListFilters, get_encounter_detail, list_encounters
from figure_data.encounters.types import EncounterOperationError


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
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return MappingResult(self.rows)


def summary_row() -> dict[str, Any]:
    return {
        "encounter_id": UUID("00000000-0000-0000-0000-000000000001"),
        "person_a_name": "諸葛亮",
        "person_b_name": "司馬懿",
        "encounter_kind": "direct_interaction",
        "certainty_level": "high",
        "path_eligible": True,
        "source_work_id": 1,
        "pages": "12a",
        "status": "active",
        "reviewed_by": "lyl",
        "reviewed_at": datetime.now(UTC),
    }


def test_list_encounters_builds_filters() -> None:
    session = FakeSession([summary_row()])

    rows = list_encounters(
        session,  # type: ignore[arg-type]
        EncounterListFilters(status="active", path_eligible=True, limit=5),
    )

    assert rows[0].person_a_name == "諸葛亮"
    assert "e.status = :status" in session.statements[0]
    assert "e.path_eligible = :path_eligible" in session.statements[0]
    params = session.params[0]
    assert params is not None
    assert params["limit"] == 5


def test_get_encounter_detail_raises_when_missing() -> None:
    session = FakeSession([])

    with raises(EncounterOperationError, match="encounter not found"):
        get_encounter_detail(
            session,  # type: ignore[arg-type]
            UUID("00000000-0000-0000-0000-000000000001"),
        )
