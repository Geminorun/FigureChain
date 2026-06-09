from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.expansion.types import EncounterExpansionReport, EncounterExpansionReportRow


@dataclass(frozen=True)
class EncounterExpansionReportFilters:
    reviewed_since: str | None = None
    limit: int = 200


def export_encounter_expansion_report(
    session: Session,
    filters: EncounterExpansionReportFilters,
) -> EncounterExpansionReport:
    params: dict[str, Any] = {"limit": filters.limit}
    reviewed_since_sql = ""
    if filters.reviewed_since:
        reviewed_since_sql = "and e.reviewed_at >= :reviewed_since"
        params["reviewed_since"] = filters.reviewed_since
    rows = (
        session.execute(
            text(
                f"""
                select
                  e.id::text as encounter_id,
                  ee.candidate_table,
                  ee.candidate_id,
                  coalesce(
                    pa.primary_name_zh_hant,
                    pa.primary_name_zh_hans,
                    pa.primary_name_romanized,
                    e.person_a_id::text
                  ) as person_a_name,
                  coalesce(
                    pb.primary_name_zh_hant,
                    pb.primary_name_zh_hans,
                    pb.primary_name_romanized,
                    e.person_b_id::text
                  ) as person_b_name,
                  e.person_a_id::text,
                  e.person_b_id::text,
                  e.encounter_kind,
                  e.certainty_level,
                  e.path_eligible,
                  e.source_work_id,
                  ee.source_ref_id,
                  e.pages,
                  e.evidence_summary,
                  e.reviewed_by,
                  e.reviewed_at
                from figure_data.encounters e
                left join figure_data.encounter_evidence ee on ee.encounter_id = e.id
                left join figure_data.persons pa on pa.id = e.person_a_id
                left join figure_data.persons pb on pb.id = e.person_b_id
                where e.status = 'active'
                  and e.path_eligible = true
                  and e.certainty_level = 'high'
                  and e.encounter_kind = 'direct_interaction'
                  {reviewed_since_sql}
                order by e.reviewed_at desc, e.id, ee.id
                limit :limit
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    return EncounterExpansionReport(
        generated_at=datetime.now(UTC).isoformat(),
        reviewed_since=filters.reviewed_since,
        rows=tuple(report_row_from_mapping(cast(Mapping[str, Any], row)) for row in rows),
    )


def report_row_from_mapping(row: Mapping[str, Any]) -> EncounterExpansionReportRow:
    return EncounterExpansionReportRow(
        encounter_id=str(row["encounter_id"]),
        candidate_table=row["candidate_table"],
        candidate_id=row["candidate_id"],
        person_a_name=str(row["person_a_name"]),
        person_b_name=str(row["person_b_name"]),
        person_a_id=str(row["person_a_id"]),
        person_b_id=str(row["person_b_id"]),
        encounter_kind=str(row["encounter_kind"]),
        certainty_level=str(row["certainty_level"]),
        path_eligible=bool(row["path_eligible"]),
        source_work_id=row["source_work_id"],
        source_ref_id=row["source_ref_id"],
        pages=row["pages"],
        evidence_summary=str(row["evidence_summary"]),
        reviewed_by=str(row["reviewed_by"]),
        reviewed_at=row["reviewed_at"].isoformat(),
    )
