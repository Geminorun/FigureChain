from __future__ import annotations

from dataclasses import dataclass

from figure_data.runtime.diagnostics import (
    DependencyDiagnostic,
    RuntimeDiagnostics,
    dependency_status,
    runtime_config_summary,
)


@dataclass(frozen=True)
class FakeSettings:
    database_url: str = "postgresql+psycopg://user:secret@localhost/figure"
    neo4j_uri: str | None = "bolt://localhost:7687"
    neo4j_user: str | None = "neo4j"
    neo4j_password: str | None = "secret"
    redis_url: str | None = "redis://:secret@localhost:6379/0"
    ai_enabled: bool = False
    ai_provider: str | None = "fake"
    ai_allow_real_provider: bool = False
    ai_model: str | None = "fake-history-model"


def test_runtime_config_summary_redacts_sensitive_values() -> None:
    summary = runtime_config_summary(FakeSettings())

    text = repr(summary)
    assert "secret" not in text
    assert "postgresql+psycopg://" not in text
    assert "redis://:secret" not in text
    assert summary["database_url"] == "[REDACTED]"
    assert summary["redis_url"] == "[REDACTED]"
    assert summary["ai_provider"] == "fake"


def test_dependency_status_maps_exceptions_to_error() -> None:
    def failing_check() -> None:
        raise RuntimeError("postgresql://user:secret@localhost/db failed")

    result = dependency_status("postgresql", failing_check)

    assert result.name == "postgresql"
    assert result.status == "error"
    assert "secret" not in result.message
    assert "[REDACTED]" in result.message


def test_runtime_diagnostics_overall_status() -> None:
    diagnostics = RuntimeDiagnostics(
        config={"ai_provider": "fake"},
        dependencies=[
            DependencyDiagnostic(name="postgresql", status="ok", message=None),
            DependencyDiagnostic(name="neo4j", status="error", message="unavailable"),
        ],
    )

    assert diagnostics.status == "degraded"
