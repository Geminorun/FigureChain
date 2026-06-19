from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from figure_data.ai.provider import create_ai_provider
from figure_data.ai.redaction import redact_sensitive_text


class ProjectionBatchLike(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def started_at(self) -> datetime: ...

    @property
    def finished_at(self) -> datetime | None: ...

    @property
    def validation_status(self) -> str: ...


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
        if not self.dependencies:
            return "degraded"
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


def collect_runtime_diagnostics(
    *,
    settings: object,
    postgresql_check: Callable[[], None],
    neo4j_check: Callable[[], None],
    redis_check: Callable[[], None] | None = None,
    graph_batch_check: Callable[[], DependencyDiagnostic] | None = None,
) -> RuntimeDiagnostics:
    dependencies = [
        dependency_status("postgresql", postgresql_check),
        dependency_status("neo4j", neo4j_check),
        _redis_rq_status(settings, redis_check),
        _ai_provider_status(settings),
    ]
    if graph_batch_check is not None:
        dependencies.append(graph_batch_check())
    else:
        dependencies.append(
            DependencyDiagnostic(
                name="graph_projection_batch",
                status="warning",
                message="latest graph projection batch was not checked",
            )
        )
    return RuntimeDiagnostics(
        config=runtime_config_summary(settings),
        dependencies=dependencies,
    )


def projection_batch_status(
    *,
    latest_success: ProjectionBatchLike | None,
    latest_failed: ProjectionBatchLike | None,
) -> DependencyDiagnostic:
    if latest_success is None:
        if latest_failed is None:
            return DependencyDiagnostic(
                name="graph_projection_batch",
                status="warning",
                message="no graph projection batch has succeeded yet",
            )
        return DependencyDiagnostic(
            name="graph_projection_batch",
            status="error",
            message=f"latest_success=none latest_failed={latest_failed.id}",
        )
    if latest_failed is not None and latest_failed.started_at > latest_success.started_at:
        return DependencyDiagnostic(
            name="graph_projection_batch",
            status="error",
            message=f"latest_success={latest_success.id} latest_failed={latest_failed.id}",
        )
    return DependencyDiagnostic(
        name="graph_projection_batch",
        status="ok",
        message=(
            f"latest_success={latest_success.id} "
            f"validation_status={latest_success.validation_status}"
        ),
    )


def _redis_rq_status(
    settings: object,
    redis_check: Callable[[], None] | None,
) -> DependencyDiagnostic:
    backend = getattr(settings, "ai_queue_backend", "database")
    if backend != "rq":
        return DependencyDiagnostic(
            name="redis_rq",
            status="ok",
            message=f"queue_backend={backend}",
        )
    if getattr(settings, "redis_url", None) is None:
        return DependencyDiagnostic(
            name="redis_rq",
            status="error",
            message="REDIS_URL is required when queue_backend=rq",
        )
    if redis_check is None:
        return DependencyDiagnostic(
            name="redis_rq",
            status="warning",
            message="redis connectivity was not checked",
        )
    return dependency_status("redis_rq", redis_check)


def _ai_provider_status(settings: object) -> DependencyDiagnostic:
    try:
        provider = create_ai_provider(settings)  # type: ignore[arg-type]
    except Exception as exc:
        return DependencyDiagnostic(
            name="ai_provider",
            status="error",
            message=redact_sensitive_text(str(exc)),
        )
    provider_name = getattr(provider, "provider_name", "unknown")
    return DependencyDiagnostic(
        name="ai_provider",
        status="ok",
        message=f"provider={provider_name}",
    )
