from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.ai.retrieval_service import (
    BuildRagIndexResult,
    SearchRagEvidenceResult,
)
from figure_data.cli import app

runner = CliRunner()


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


def patch_session(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr(
        "figure_data.cli.create_session_factory",
        lambda settings: lambda: DummySession(),
    )


def test_rag_cli_help_commands_exit_zero() -> None:
    for command in ("build-rag-index", "search-rag-evidence"):
        result = runner.invoke(app, [command, "--help"])

        assert result.exit_code == 0


def test_build_rag_index_command_outputs_counts(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.build_rag_index",
        lambda **kwargs: BuildRagIndexResult(
            sources_read=1,
            documents_indexed=1,
            embeddings_written=1,
            provider="fake",
            model_name="fake-hash-embedding",
        ),
    )

    result = runner.invoke(
        app,
        ["build-rag-index", "--source-ref-id", "3853784", "--limit", "5"],
    )

    assert result.exit_code == 0
    assert "rag_index\tsources_read\t1" in result.output


def test_search_rag_evidence_command_requires_query(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)

    result = runner.invoke(app, ["search-rag-evidence", "--query", " "])

    assert result.exit_code == 1
    assert "query is required" in result.stderr


def test_search_rag_evidence_command_outputs_results(monkeypatch: MonkeyPatch) -> None:
    patch_session(monkeypatch)
    monkeypatch.setattr(
        "figure_data.cli.search_rag_evidence",
        lambda **kwargs: SearchRagEvidenceResult(
            query="许几 韩琦",
            provider="fake",
            model_name="fake-hash-embedding",
            results=[],
        ),
    )

    result = runner.invoke(app, ["search-rag-evidence", "--query", "许几 韩琦"])

    assert result.exit_code == 0
    assert "rag_query\t许几 韩琦" in result.output
