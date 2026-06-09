from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.graph.types import ChainEdge, ChainLookupResult, ChainPath, ChainPerson


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


def patch_find_chain(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr("figure_data.cli.create_neo4j_driver", lambda settings: DummyDriver())
    monkeypatch.setattr(
        "figure_data.cli.get_neo4j_config",
        lambda settings: type("C", (), {"database": "neo4j"})(),
    )
    monkeypatch.setattr("figure_data.cli.graph_session", lambda driver, database: DummySession())
    monkeypatch.setattr(
        "figure_data.cli.find_chain",
        lambda pg_session, graph_session, source, target, max_depth: ChainLookupResult(
            source_person_id="person-a",
            target_person_id="person-b",
            max_depth=12,
            path=ChainPath(
                people=(
                    ChainPerson("person-a", "諸葛亮", 181, 234, "25403"),
                    ChainPerson("person-b", "司馬懿", 178, 251, "21204"),
                ),
                edges=(
                    ChainEdge(
                        "encounter-1",
                        "direct_interaction",
                        "high",
                        "12a",
                        "二人有直接互动",
                    ),
                ),
            ),
        ),
    )


def test_find_chain_command_is_registered() -> None:
    result = CliRunner().invoke(app, ["find-chain", "--help"])

    assert result.exit_code == 0
    assert "find-chain" in result.output


def test_find_chain_outputs_chain(monkeypatch: MonkeyPatch) -> None:
    patch_find_chain(monkeypatch)

    result = CliRunner().invoke(app, ["find-chain", "--from", "诸葛亮", "--to", "司马懿"])

    assert result.exit_code == 0
    assert "chain\tlength=1" in result.output
    assert "encounter-1" in result.output
