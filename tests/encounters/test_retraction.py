from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pytest import raises

from figure_data.encounters.retraction import retract_encounter
from figure_data.encounters.types import EncounterOperationError, EncounterRetractionOptions


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
    def __init__(self, encounter_status: str = "active") -> None:
        self.encounter_status = encounter_status
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        sql = str(statement)
        if "from figure_data.encounters" in sql and "select status" in sql:
            return MappingResult([{"status": self.encounter_status}])
        if "from figure_data.encounter_evidence" in sql:
            return MappingResult(
                [
                    {
                        "candidate_table": "relationship_candidates",
                        "candidate_id": 123,
                    }
                ]
            )
        return MappingResult([])


def test_retract_encounter_updates_encounter_and_linked_candidates() -> None:
    encounter_id = UUID("00000000-0000-0000-0000-000000000001")
    session = FakeSession()

    result = retract_encounter(
        session,  # type: ignore[arg-type]
        EncounterRetractionOptions(
            encounter_id=encounter_id,
            reviewed_by="lyl",
            note="证据不足",
        ),
    )

    joined_sql = "\n".join(session.statements)
    assert result.path_eligible is False
    assert result.linked_candidates_updated == 1
    assert "status = :status" in joined_sql
    assert "path_eligible = false" in joined_sql
    assert "review_status = :review_status" in joined_sql
    assert "promoted_encounter_id" not in joined_sql.split("review_status = :review_status")[-1]


def test_retract_encounter_refuses_already_retracted_without_force() -> None:
    encounter_id = UUID("00000000-0000-0000-0000-000000000001")
    session = FakeSession(encounter_status="retracted")

    with raises(EncounterOperationError, match="encounter is already retracted"):
        retract_encounter(
            session,  # type: ignore[arg-type]
            EncounterRetractionOptions(
                encounter_id=encounter_id,
                reviewed_by="lyl",
                note="证据不足",
            ),
        )
