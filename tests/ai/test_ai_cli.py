from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.ai.errors import AIRunNotFoundError
from figure_data.ai.types import AIRunRecord
from figure_data.cli import app


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


def ai_run_record() -> AIRunRecord:
    return AIRunRecord(
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
        purpose="ai_foundation_diagnostic",
        provider="fake",
        model_name="fake-model",
        prompt_version_id=UUID("00000000-0000-0000-0000-000000000002"),
        prompt_key="ai_foundation_diagnostic",
        prompt_version="2026-06-13.1",
        input_hash="abc123",
        input_snapshot={"echo_id": "abc"},
        output_snapshot={"message": "ready", "echo_id": "abc", "warnings": []},
        raw_output_excerpt='{"message":"ready"}',
        status="succeeded",
        schema_valid=True,
        error_code=None,
        error_message=None,
        started_at=datetime(2026, 6, 13, tzinfo=UTC),
        finished_at=datetime(2026, 6, 13, tzinfo=UTC),
        created_by="test",
    )


def test_inspect_ai_run_command_outputs_trace(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr("figure_data.cli.get_ai_run", lambda session, run_id: ai_run_record())

    result = CliRunner().invoke(
        app,
        ["inspect-ai-run", "--id", "00000000-0000-0000-0000-000000000001"],
    )

    assert result.exit_code == 0
    assert "ai_run\t00000000-0000-0000-0000-000000000001" in result.output
    assert "status\tsucceeded" in result.output


def test_inspect_ai_run_command_exits_nonzero_when_missing(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)

    def raise_missing(session: object, run_id: UUID) -> AIRunRecord:
        raise AIRunNotFoundError(f"AI run not found: {run_id}")

    monkeypatch.setattr("figure_data.cli.get_ai_run", raise_missing)

    result = CliRunner().invoke(
        app,
        ["inspect-ai-run", "--id", "00000000-0000-0000-0000-000000000001"],
    )

    assert result.exit_code == 1
    assert "AI run not found" in result.stderr
