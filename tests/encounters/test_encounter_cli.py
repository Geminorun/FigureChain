from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.db.enums import EncounterStatus
from figure_data.encounters.types import (
    EncounterPromotionResult,
    EncounterRetractionResult,
    EncounterSummary,
)
from figure_data.review.types import CandidateKind


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
    monkeypatch.setattr("figure_data.cli.session_scope", lambda factory: DummySession())


def test_encounter_commands_are_registered() -> None:
    for command in (
        "promote-encounter",
        "list-encounters",
        "inspect-encounter",
        "retract-encounter",
    ):
        result = CliRunner().invoke(app, [command, "--help"])

        assert result.exit_code == 0
        assert command in result.output


def test_promote_encounter_outputs_result(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    encounter_id = UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(
        "figure_data.cli.promote_candidate_to_encounter",
        lambda session, options: EncounterPromotionResult(
            encounter_id=encounter_id,
            candidate_kind=CandidateKind.RELATIONSHIP,
            candidate_id=123,
            encounter_kind="direct_interaction",
            certainty_level="high",
            path_eligible=True,
            reused_existing=False,
        ),
    )

    result = CliRunner().invoke(
        app,
        [
            "promote-encounter",
            "--kind",
            "relationship",
            "--id",
            "123",
            "--reviewed-by",
            "lyl",
            "--evidence-summary",
            "CBDB 关系代码显示两人有直接互动",
        ],
    )

    assert result.exit_code == 0
    assert f"promoted\t{encounter_id}\trelationship\t123" in result.output


def test_list_encounters_outputs_rows(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    encounter_id = UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(
        "figure_data.cli.list_encounters",
        lambda session, filters: [
            EncounterSummary(
                encounter_id=encounter_id,
                person_a_name="諸葛亮",
                person_b_name="司馬懿",
                encounter_kind="direct_interaction",
                certainty_level="high",
                path_eligible=True,
                source_work_id=1,
                pages="12a",
                status="active",
                reviewed_by="lyl",
                reviewed_at=datetime.now(UTC),
            )
        ],
    )

    result = CliRunner().invoke(app, ["list-encounters", "--status", "active"])

    assert result.exit_code == 0
    assert "encounter_id\tperson_a\tperson_b" in result.output
    assert f"{encounter_id}\t諸葛亮\t司馬懿" in result.output


def test_retract_encounter_outputs_result(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    encounter_id = UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(
        "figure_data.cli.retract_encounter",
        lambda session, options: EncounterRetractionResult(
            encounter_id=encounter_id,
            status=EncounterStatus.RETRACTED,
            path_eligible=False,
            linked_candidates_updated=1,
        ),
    )

    result = CliRunner().invoke(
        app,
        [
            "retract-encounter",
            "--id",
            str(encounter_id),
            "--reviewed-by",
            "lyl",
            "--note",
            "证据不足",
        ],
    )

    assert result.exit_code == 0
    assert f"retracted\t{encounter_id}\tlinked_candidates_updated=1" in result.output
