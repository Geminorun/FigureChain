from __future__ import annotations

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data.cli import app
from figure_data.runtime.diagnostics import DependencyDiagnostic, RuntimeDiagnostics


def test_doctor_command_outputs_redacted_runtime_summary(
    monkeypatch: MonkeyPatch,
) -> None:
    diagnostics = RuntimeDiagnostics(
        config={
            "database_url": "[REDACTED]",
            "redis_url": "[REDACTED]",
            "ai_provider": "fake",
        },
        dependencies=[
            DependencyDiagnostic(name="postgresql", status="ok"),
            DependencyDiagnostic(
                name="neo4j",
                status="error",
                message="Neo4j is unavailable",
            ),
        ],
    )
    monkeypatch.setattr(
        "figure_data.cli.collect_runtime_diagnostics",
        lambda: diagnostics,
    )

    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "runtime_status\tdegraded" in result.output
    assert "config\tdatabase_url\t[REDACTED]" in result.output
    assert "dependency\tpostgresql\tok" in result.output
    assert "dependency\tneo4j\terror\tNeo4j is unavailable" in result.output


def test_doctor_command_does_not_print_secret_text(monkeypatch: MonkeyPatch) -> None:
    diagnostics = RuntimeDiagnostics(
        config={"database_url": "[REDACTED]"},
        dependencies=[
            DependencyDiagnostic(name="redis", status="error", message="[REDACTED]")
        ],
    )
    monkeypatch.setattr(
        "figure_data.cli.collect_runtime_diagnostics",
        lambda: diagnostics,
    )

    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "postgresql://user:secret" not in result.output
    assert "redis://:secret" not in result.output
