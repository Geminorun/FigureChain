from typer.testing import CliRunner

from figure_data.cli import app


def test_search_person_requires_query() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["search-person"])

    assert result.exit_code != 0
    assert "No such command" not in result.output
    assert "Missing argument" in result.output
