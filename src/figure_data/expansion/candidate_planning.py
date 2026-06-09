from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.expansion.types import ExpansionCandidate


@dataclass(frozen=True)
class ExpansionCandidateFilters:
    review_status: str | None = "unreviewed"
    limit: int = 50


def plan_encounter_expansion(
    session: Session,
    filters: ExpansionCandidateFilters,
) -> list[ExpansionCandidate]:
    params: dict[str, Any] = {"limit": filters.limit}
    status_filter = ""
    if filters.review_status:
        status_filter = "and rc.review_status = :review_status"
        params["review_status"] = filters.review_status

    rows = (
        session.execute(
            text(
                f"""
                with active_path_people as (
                  select person_a_id as person_id
                  from figure_data.encounters
                  where status = 'active'
                    and path_eligible = true
                    and certainty_level = 'high'
                    and encounter_kind = 'direct_interaction'
                  union
                  select person_b_id as person_id
                  from figure_data.encounters
                  where status = 'active'
                    and path_eligible = true
                    and certainty_level = 'high'
                    and encounter_kind = 'direct_interaction'
                )
                select
                  rc.id as candidate_id,
                  rc.person_a_id::text as person_a_id,
                  rc.person_b_id::text as person_b_id,
                  coalesce(
                    pa.primary_name_zh_hant,
                    pa.primary_name_zh_hans,
                    pa.primary_name_romanized
                  ) as person_a_name,
                  coalesce(
                    pb.primary_name_zh_hant,
                    pb.primary_name_zh_hans,
                    pb.primary_name_romanized
                  ) as person_b_name,
                  rc.cbdb_person_a_id,
                  rc.cbdb_person_b_id,
                  rc.candidate_strength,
                  rc.candidate_basis,
                  rc.association_label as relation_label,
                  rc.source_work_id,
                  null::integer as source_ref_id,
                  rc.pages,
                  rc.review_status,
                  (
                    case when apa.person_id is null then 0 else 1 end
                    + case when apb.person_id is null then 0 else 1 end
                  ) as active_path_neighbors,
                  (
                    100
                    + case when rc.source_work_id is null then 0 else 20 end
                    + case when rc.pages is null or btrim(rc.pages) = '' then 0 else 10 end
                    + (
                      case when apa.person_id is null then 0 else 1 end
                      + case when apb.person_id is null then 0 else 1 end
                    ) * 5
                  ) as score
                from figure_data.relationship_candidates rc
                left join figure_data.persons pa on pa.id = rc.person_a_id
                left join figure_data.persons pb on pb.id = rc.person_b_id
                left join active_path_people apa on apa.person_id = rc.person_a_id
                left join active_path_people apb on apb.person_id = rc.person_b_id
                where rc.candidate_strength = 'high'
                  and rc.candidate_basis = 'direct_interaction_likely'
                  and rc.person_a_id is not null
                  and rc.person_b_id is not null
                  and rc.person_a_id <> rc.person_b_id
                  {status_filter}
                order by score desc, active_path_neighbors desc, rc.id
                limit :limit
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [expansion_candidate_from_row(cast(Mapping[str, Any], row)) for row in rows]


def expansion_candidate_from_row(row: Mapping[str, Any]) -> ExpansionCandidate:
    return ExpansionCandidate(
        candidate_id=int(row["candidate_id"]),
        person_a_id=str(row["person_a_id"]),
        person_b_id=str(row["person_b_id"]),
        person_a_name=row["person_a_name"],
        person_b_name=row["person_b_name"],
        cbdb_person_a_id=row["cbdb_person_a_id"],
        cbdb_person_b_id=row["cbdb_person_b_id"],
        candidate_strength=str(row["candidate_strength"]),
        candidate_basis=str(row["candidate_basis"]),
        relation_label=row["relation_label"],
        source_work_id=row["source_work_id"],
        source_ref_id=row["source_ref_id"],
        pages=row["pages"],
        review_status=str(row["review_status"]),
        active_path_neighbors=int(row["active_path_neighbors"]),
        score=int(row["score"]),
    )
