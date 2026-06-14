from pathlib import Path

from typer.testing import CliRunner

from figure_data.cli import app

runner = CliRunner()


def test_evaluate_ai_samples_help_exits_zero() -> None:
    result = runner.invoke(app, ["evaluate-ai-samples", "--help"])

    assert result.exit_code == 0
    assert "evaluate-ai-samples" in result.output
    assert "--resolve-ai-runs" in result.output
    assert "--fixture-only" in result.output


def test_evaluate_ai_samples_writes_markdown_report(tmp_path: Path) -> None:
    output = tmp_path / "stage4.md"

    result = runner.invoke(
        app,
        [
            "evaluate-ai-samples",
            "--fixture",
            "docs/superpowers/evaluation/stage4-ai-samples.json",
            "--evidence",
            "docs/superpowers/evaluation/stage4-acceptance-evidence.example.json",
            "--output",
            str(output),
            "--fixture-only",
        ],
    )

    assert result.exit_code == 0
    assert f"evaluation_report\t{output}" in result.output
    assert "samples\t4" in result.output
    assert "recommendation\tblocked_pending_validation" in result.output
    assert output.read_text(encoding="utf-8").startswith("# 阶段 4 AI 评测与验收报告")


def test_evaluate_ai_samples_exits_nonzero_for_invalid_fixture(tmp_path: Path) -> None:
    fixture = tmp_path / "invalid.json"
    fixture.write_text("{not json", encoding="utf-8")
    output = tmp_path / "stage4.md"

    result = runner.invoke(
        app,
        [
            "evaluate-ai-samples",
            "--fixture",
            str(fixture),
            "--output",
            str(output),
            "--fixture-only",
        ],
    )

    assert result.exit_code == 1
    assert str(fixture) in result.stderr
    assert not output.exists()
