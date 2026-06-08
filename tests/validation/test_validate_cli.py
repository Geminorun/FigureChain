from typer.testing import CliRunner

from figure_data.cli import app


def test_validate_cbdb_command_is_registered() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["validate-cbdb", "--help"])

    assert result.exit_code == 0
    assert "validate-cbdb" in result.output
