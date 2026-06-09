from __future__ import annotations

from collections.abc import Iterable

from figure_data.graph.types import ProjectionStats
from figure_data.validation.report import ValidationCheck


def format_projection_stats(stats: ProjectionStats) -> list[str]:
    return [
        f"persons_projected={stats.persons_projected}",
        f"encounters_projected={stats.encounters_projected}",
        f"relationships_projected={stats.relationships_projected}",
        f"started_at={stats.started_at.isoformat()}",
        f"finished_at={stats.finished_at.isoformat()}",
    ]


def format_validation_checks(checks: Iterable[ValidationCheck]) -> list[str]:
    lines: list[str] = []
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        lines.append(f"{status}\t{check.name}\t{check.detail}")
    return lines
