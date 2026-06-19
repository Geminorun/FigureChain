from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from figure_data.ai.redaction import redact_sensitive_text


@dataclass(frozen=True)
class DependencyDiagnostic:
    name: str
    status: str
    message: str | None = None


@dataclass(frozen=True)
class RuntimeDiagnostics:
    config: dict[str, object]
    dependencies: list[DependencyDiagnostic]

    @property
    def status(self) -> str:
        if all(item.status == "ok" for item in self.dependencies):
            return "ok"
        return "degraded"


def runtime_config_summary(settings: object) -> dict[str, object]:
    database_url = getattr(settings, "database_url", None)
    redis_url = getattr(settings, "redis_url", None)
    return {
        "database_url": "[REDACTED]" if database_url else None,
        "neo4j_uri": getattr(settings, "neo4j_uri", None),
        "neo4j_user": getattr(settings, "neo4j_user", None),
        "neo4j_password": (
            "[REDACTED]" if getattr(settings, "neo4j_password", None) else None
        ),
        "redis_url": "[REDACTED]" if redis_url else None,
        "ai_enabled": bool(getattr(settings, "ai_enabled", False)),
        "ai_provider": getattr(settings, "ai_provider", None),
        "ai_allow_real_provider": bool(
            getattr(settings, "ai_allow_real_provider", False)
        ),
        "ai_model": getattr(settings, "ai_model", None),
    }


def dependency_status(
    name: str,
    check: Callable[[], None],
) -> DependencyDiagnostic:
    try:
        check()
    except Exception as exc:
        return DependencyDiagnostic(
            name=name,
            status="error",
            message=redact_sensitive_text(str(exc)),
        )
    return DependencyDiagnostic(name=name, status="ok")
