from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.validation.report import ValidationCheck


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


def test_validate_encounters_command_is_registered() -> None:
    result = CliRunner().invoke(app, ["validate-encounters", "--help"])

    assert result.exit_code == 0
    assert "validate-encounters" in result.output


def test_validate_encounters_outputs_checks(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr(
        "figure_data.cli.validate_encounters",
        lambda session: [ValidationCheck("encounters:no_self_loops", True, "violations=0")],
    )

    result = CliRunner().invoke(app, ["validate-encounters"])

    assert result.exit_code == 0
    assert "PASS\tencounters:no_self_loops\tviolations=0" in result.output


def test_validate_encounters_exits_nonzero_on_failure(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr(
        "figure_data.cli.validate_encounters",
        lambda session: [ValidationCheck("encounters:active_have_evidence", False, "violations=1")],
    )

    result = CliRunner().invoke(app, ["validate-encounters"])

    assert result.exit_code == 1
    assert "FAIL\tencounters:active_have_evidence\tviolations=1" in result.output
