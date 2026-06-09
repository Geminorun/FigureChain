from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.expansion.types import ExpansionCandidate


class DummySession:
    def __enter__(self) -> object:
        return object()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


def patch_session(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)


def test_plan_encounter_expansion_command_outputs_rows(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.plan_encounter_expansion",
        lambda session, filters: [
            ExpansionCandidate(
                candidate_id=960664,
                person_a_id="person-a",
                person_b_id="person-b",
                person_a_name="許幾",
                person_b_name="韓琦",
                cbdb_person_a_id=780,
                cbdb_person_b_id=630,
                candidate_strength="high",
                candidate_basis="direct_interaction_likely",
                relation_label="谒",
                source_work_id=7596,
                source_ref_id=3853784,
                pages="11905",
                review_status="unreviewed",
                active_path_neighbors=1,
                score=135,
            )
        ],
    )

    result = CliRunner().invoke(app, ["plan-encounter-expansion", "--limit", "5"])

    assert result.exit_code == 0
    assert "candidate_id\tperson_a\tperson_b" in result.output
    assert "960664\t許幾\t韓琦" in result.output
