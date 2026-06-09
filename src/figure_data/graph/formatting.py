from __future__ import annotations

from collections.abc import Iterable

from figure_data.graph.types import ChainLookupResult, ChainPath, ProjectionStats
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


def format_chain_result(result: ChainLookupResult) -> list[str]:
    if result.path is None:
        return [
            "no_path"
            f"\tfrom={result.source_person_id}"
            f"\tto={result.target_person_id}"
            f"\tmax_depth={result.max_depth}"
        ]
    return format_chain_path(result.path)


def format_chain_path(path: ChainPath) -> list[str]:
    lines = [f"chain\tlength={path.length}"]
    for index, person in enumerate(path.people):
        years = _format_years(person.birth_year, person.death_year)
        cbdb = person.cbdb_external_id or ""
        lines.append(f"person\t{person.person_id}\t{person.display_name}\t{years}\tcbdb={cbdb}")
        if index < len(path.edges):
            edge = path.edges[index]
            pages = edge.pages or ""
            lines.append(
                f"edge\t{edge.encounter_id}\t{edge.encounter_kind}\t{edge.certainty_level}"
                f"\tpages={pages}\tsummary={edge.evidence_summary}"
            )
    return lines


def _format_years(birth_year: int | None, death_year: int | None) -> str:
    birth = "" if birth_year is None else str(birth_year)
    death = "" if death_year is None else str(death_year)
    return f"{birth}-{death}"
