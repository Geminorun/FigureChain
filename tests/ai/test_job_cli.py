from types import TracebackType
from uuid import UUID

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.ai.job_runner import AIGenerationJobFailure, AIGenerationJobRunSummary
from figure_data.cli import app

runner = CliRunner()


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
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: object())
    monkeypatch.setattr("figure_data.cli.session_scope", lambda factory: DummySession())


def test_run_ai_jobs_help_is_registered() -> None:
    result = runner.invoke(app, ["run-ai-jobs", "--help"])

    assert result.exit_code == 0
    assert "--limit" in result.output
    assert "--job-type" in result.output


def test_run_ai_jobs_command_outputs_summary(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    calls: list[tuple[int, str | None]] = []

    def fake_run_ai_jobs(**kwargs: object) -> AIGenerationJobRunSummary:
        calls.append((kwargs["limit"], kwargs["job_type"]))  # type: ignore[arg-type]
        return AIGenerationJobRunSummary(
            claimed_count=2,
            succeeded_count=1,
            failed_count=1,
            failures=[
                AIGenerationJobFailure(
                    job_id=UUID("00000000-0000-0000-0000-000000000501"),
                    error_code="candidate_not_found",
                    error_message="candidate not found",
                )
            ],
        )

    monkeypatch.setattr("figure_data.cli.run_ai_jobs", fake_run_ai_jobs)

    result = runner.invoke(
        app,
        ["run-ai-jobs", "--limit", "2", "--job-type", "candidate_review_suggestion"],
    )

    assert result.exit_code == 0
    assert calls == [(2, "candidate_review_suggestion")]
    assert "ai_jobs\tclaimed=2\tsucceeded=1\tfailed=1" in result.output
    assert "failed_job\t00000000-0000-0000-0000-000000000501\tcandidate_not_found" in result.output


def test_run_ai_jobs_command_rejects_unknown_job_type(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)

    result = runner.invoke(app, ["run-ai-jobs", "--job-type", "unknown"])

    assert result.exit_code == 1
    assert "unsupported AI job type: unknown" in result.stderr
