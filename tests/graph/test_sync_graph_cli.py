from datetime import datetime
from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.graph.types import IncrementalProjectionStats, ProjectionStats


class DummyDriver:
    def close(self) -> None:
        return None


class DummyPgSession:
    def __enter__(self) -> object:
        return object()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class DummyGraphSession(DummyPgSession):
    pass


def test_sync_graph_command_is_registered() -> None:
    result = CliRunner().invoke(app, ["sync-graph", "--help"])

    assert result.exit_code == 0
    assert "sync-graph" in result.output


def test_sync_graph_requires_rebuild_flag() -> None:
    result = CliRunner().invoke(app, ["sync-graph"])

    assert result.exit_code == 1
    assert "--rebuild or --incremental is required" in result.output


def test_sync_graph_rejects_conflicting_modes() -> None:
    result = CliRunner().invoke(app, ["sync-graph", "--rebuild", "--incremental"])

    assert result.exit_code == 1
    assert "choose exactly one graph sync mode" in result.output


def test_sync_graph_outputs_projection_stats(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummyPgSession)
    monkeypatch.setattr("figure_data.cli.create_neo4j_driver", lambda settings: DummyDriver())
    monkeypatch.setattr(
        "figure_data.cli.get_neo4j_config",
        lambda settings: type("C", (), {"database": "neo4j"})(),
    )
    monkeypatch.setattr(
        "figure_data.cli.graph_session",
        lambda driver, database: DummyGraphSession(),
    )
    monkeypatch.setattr(
        "figure_data.cli.sync_graph_rebuild",
        lambda pg_session, neo4j_session: ProjectionStats(
            persons_projected=2,
            encounters_projected=1,
            relationships_projected=1,
            started_at=datetime(2026, 6, 9),
            finished_at=datetime(2026, 6, 9),
        ),
    )

    result = CliRunner().invoke(app, ["sync-graph", "--rebuild"])

    assert result.exit_code == 0
    assert "persons_projected=2" in result.output
    assert "relationships_projected=1" in result.output


def test_sync_graph_outputs_incremental_projection_stats(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummyPgSession)
    monkeypatch.setattr("figure_data.cli.create_neo4j_driver", lambda settings: DummyDriver())
    monkeypatch.setattr(
        "figure_data.cli.get_neo4j_config",
        lambda settings: type("C", (), {"database": "neo4j"})(),
    )
    monkeypatch.setattr(
        "figure_data.cli.graph_session",
        lambda driver, database: DummyGraphSession(),
    )
    monkeypatch.setattr(
        "figure_data.cli.sync_graph_incremental",
        lambda pg_session, neo4j_session: IncrementalProjectionStats(
            persons_written=2,
            encounters_seen=3,
            relationships_written=1,
            relationships_deleted=2,
            started_at=datetime(2026, 6, 9),
            finished_at=datetime(2026, 6, 9),
        ),
    )

    result = CliRunner().invoke(app, ["sync-graph", "--incremental"])

    assert result.exit_code == 0
    assert "encounters_seen=3" in result.output
    assert "relationships_deleted=2" in result.output
