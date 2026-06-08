from types import TracebackType

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.search.person_search import PersonSearchResult


def test_search_person_requires_query() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["search-person"])

    assert result.exit_code != 0
    assert "No such command" not in result.output
    assert "Missing argument" in result.output


def test_search_person_outputs_external_ids(monkeypatch: MonkeyPatch) -> None:
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

    monkeypatch.setattr("figure_data.cli.load_settings", lambda: object())
    monkeypatch.setattr("figure_data.cli.create_session_factory", lambda settings: DummySession)
    monkeypatch.setattr(
        "figure_data.cli.search_people",
        lambda session, query, limit: [
            PersonSearchResult(
                person_id="person-1",
                primary_name_zh_hant="司馬懿",
                primary_name_zh_hans="司马懿",
                primary_name_romanized="Sima Yi",
                birth_year=178,
                death_year=251,
                index_year=230,
                dynasty_code=30,
                matching_aliases=[],
                external_ids=["21204"],
            )
        ],
    )

    result = CliRunner().invoke(app, ["search-person", "Sima Yi"])

    assert result.exit_code == 0
    assert "21204" in result.output
