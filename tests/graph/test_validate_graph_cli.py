from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.validation.report import ValidationCheck


class DummyDriver:
    def close(self) -> None:
        return None


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


def patch_graph_cli(monkeypatch: MonkeyPatch, checks: list[ValidationCheck]) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr("figure_data.cli.create_neo4j_driver", lambda settings: DummyDriver())
    monkeypatch.setattr(
        "figure_data.cli.get_neo4j_config",
        lambda settings: type("C", (), {"database": "neo4j"})(),
    )
    monkeypatch.setattr("figure_data.cli.graph_session", lambda driver, database: DummySession())
    monkeypatch.setattr(
        "figure_data.cli.validate_graph",
        lambda pg_session, graph_session: checks,
    )


def test_validate_graph_command_outputs_checks(monkeypatch: MonkeyPatch) -> None:
    patch_graph_cli(
        monkeypatch,
        [ValidationCheck("graph:relationship_count", True, "postgres=1 neo4j=1")],
    )

    result = CliRunner().invoke(app, ["validate-graph"])

    assert result.exit_code == 0
    assert "PASS\tgraph:relationship_count\tpostgres=1 neo4j=1" in result.output


def test_validate_graph_exits_nonzero_on_failure(monkeypatch: MonkeyPatch) -> None:
    patch_graph_cli(
        monkeypatch,
        [ValidationCheck("graph:encounters_resolve", False, "missing=1")],
    )

    result = CliRunner().invoke(app, ["validate-graph"])

    assert result.exit_code == 1
    assert "FAIL\tgraph:encounters_resolve\tmissing=1" in result.output
