from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from figure_data.expansion.reporting import (
    EncounterExpansionReportFilters,
    export_encounter_expansion_report,
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
                    "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                    "candidate_table": "relationship_candidates",
                    "candidate_id": 960664,
                    "person_a_name": "許幾",
                    "person_b_name": "韓琦",
                    "person_a_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
                    "person_b_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
                    "encounter_kind": "direct_interaction",
                    "certainty_level": "high",
                    "path_eligible": True,
                    "source_work_id": 7596,
                    "source_ref_id": 3853784,
                    "pages": "11905",
                    "evidence_summary": "许几谒韩琦于魏",
                    "reviewed_by": "lyl",
                    "reviewed_at": datetime(2026, 6, 10, tzinfo=UTC),
                }
            ]
        )


def test_export_encounter_expansion_report_loads_reviewed_path_encounters() -> None:
    session = FakeSession()

    report = export_encounter_expansion_report(
        session,  # type: ignore[arg-type]
        EncounterExpansionReportFilters(reviewed_since="2026-06-10T00:00:00+00:00"),
    )

    assert report.generated_at.startswith("2026-")
    assert report.rows[0].encounter_id == "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"
    statement = session.statements[0]
    assert "from figure_data.encounters e" in statement
    assert "left join figure_data.encounter_evidence ee" in statement
    assert "e.reviewed_at >= :reviewed_since" in statement
    params = session.params[0]
    assert params is not None
    assert params["reviewed_since"] == "2026-06-10T00:00:00+00:00"
