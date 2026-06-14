from types import TracebackType
from uuid import UUID

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.ai.no_path_service import NoPathExplorationResult
from figure_data.ai.schemas import NoPathExplorationOutput
from figure_data.cli import app

runner = CliRunner()


class DummyDriver:
    def close(self) -> None:
        return None


class DummySession:
    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None

    def __enter__(self) -> object:
        return object()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


def patch_dependencies(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr(
        "figure_data.cli.create_session_factory",
        lambda settings: lambda: DummySession(),
    )
    monkeypatch.setattr("figure_data.cli.create_neo4j_driver", lambda settings: DummyDriver())
    monkeypatch.setattr(
        "figure_data.cli.get_neo4j_config",
        lambda settings: type("C", (), {"database": "neo4j"})(),
    )
    monkeypatch.setattr(
        "figure_data.cli.graph_session",
        lambda driver, database: DummySession(),
    )


def test_suggest_no_path_exploration_help_exits_zero() -> None:
    result = runner.invoke(app, ["suggest-no-path-exploration", "--help"])

    assert result.exit_code == 0
    assert "suggest-no-path-exploration" in result.output


def test_suggest_no_path_exploration_outputs_result(monkeypatch: MonkeyPatch) -> None:
    patch_dependencies(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.generate_no_path_exploration",
        lambda **kwargs: NoPathExplorationResult(
            ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
            output=NoPathExplorationOutput.model_validate(
                {
                    "summary": "The current projection returned no path.",
                    "likely_reasons": [],
                    "suggested_review_targets": [],
                    "retrieval_context": [],
                    "limitations": ["This is not proof of missing historical contact."],
                    "display_language": "zh-Hans",
                }
            ),
        ),
    )

    result = runner.invoke(
        app,
        [
            "suggest-no-path-exploration",
            "--from-person-id",
            "38966b03-8aa7-5143-8021-2d266889b6c5",
            "--to-person-id",
            "46cfdf66-08c4-5876-964b-4a95d098afe9",
            "--created-by",
            "tester",
            "--rag-limit",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "ai_run_id\t00000000-0000-0000-0000-000000000301" in result.output
    assert "summary\tThe current projection returned no path." in result.output
