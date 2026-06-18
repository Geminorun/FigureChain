from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.review.types import CandidateKind, CandidateSummary
from figure_data.search.person_search import search_people


@dataclass(frozen=True)
class CandidateListFilters:
    kind: CandidateKind | None = None
    person_query: str | None = None
    review_status: str | None = None
    strength: str | None = None
    basis: str | None = None
    limit: int = 20


def list_candidate_summaries(
    session: Session,
    filters: CandidateListFilters,
) -> list[CandidateSummary]:
    person_ids = _resolve_person_ids(session, filters.person_query)
    if filters.person_query is not None and not person_ids:
        return []

    params: dict[str, Any] = {"limit": filters.limit}
    where_clauses = _build_where_clauses(filters, params, person_ids)
    statements = _candidate_selects(filters.kind)
    sql = f"""
    select *
    from (
      {" union all ".join(statements)}
    ) candidates
    {where_clauses}
    order by
      case candidate_strength
        when 'high' then 1
        when 'medium' then 2
        when 'low' then 3
        else 4
      end,
      candidate_id
    limit :limit
    """
    rows = session.execute(text(sql), params).mappings().all()
    return [candidate_summary_from_row(cast(Mapping[str, Any], row)) for row in rows]


def _resolve_person_ids(session: Session, person_query: str | None) -> list[str]:
    if person_query is None or not person_query.strip():
        return []
    return [result.person_id for result in search_people(session, person_query.strip(), limit=20)]


def _build_where_clauses(
    filters: CandidateListFilters,
    params: dict[str, Any],
    person_ids: list[str],
) -> str:
    clauses: list[str] = []
    if filters.review_status:
        clauses.append("review_status = :review_status")
        params["review_status"] = filters.review_status
    if filters.strength:
        clauses.append("candidate_strength = :strength")
        params["strength"] = filters.strength
    if filters.basis:
        clauses.append("candidate_basis = :basis")
        params["basis"] = filters.basis
    if person_ids:
        clauses.append(
            "(person_a_id::text = any(:person_ids) or person_b_id::text = any(:person_ids))"
        )
        params["person_ids"] = person_ids
    if not clauses:
        return ""
    return "where " + " and ".join(clauses)


def _candidate_selects(kind: CandidateKind | None) -> list[str]:
    if kind is CandidateKind.RELATIONSHIP:
        return [_relationship_select()]
    if kind is CandidateKind.KINSHIP:
        return [_kinship_select()]
    return [_relationship_select(), _kinship_select()]


def _relationship_select() -> str:
    return """
      select
        'relationship' as candidate_kind,
        rc.id as candidate_id,
        rc.person_a_id,
        rc.person_b_id,
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
        rc.pages,
        rc.review_status
      from figure_data.relationship_candidates rc
      left join figure_data.persons pa on pa.id = rc.person_a_id
      left join figure_data.persons pb on pb.id = rc.person_b_id
    """


def _kinship_select() -> str:
    return """
      select
        'kinship' as candidate_kind,
        kc.id as candidate_id,
        kc.person_a_id,
        kc.person_b_id,
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
        null::integer as cbdb_person_a_id,
        null::integer as cbdb_person_b_id,
        kc.candidate_strength,
        kc.candidate_basis,
        coalesce(kc.kinship_label_zh, kc.kinship_label_en) as relation_label,
        kc.source_work_id,
        kc.pages,
        kc.review_status
      from figure_data.kinship_candidates kc
      left join figure_data.persons pa on pa.id = kc.person_a_id
      left join figure_data.persons pb on pb.id = kc.person_b_id
    """


def candidate_summary_from_row(row: Mapping[str, Any]) -> CandidateSummary:
    return CandidateSummary(
        candidate_kind=CandidateKind(str(row["candidate_kind"])),
        candidate_id=int(row["candidate_id"]),
        person_a_name=row["person_a_name"],
        person_b_name=row["person_b_name"],
        cbdb_person_a_id=row["cbdb_person_a_id"],
        cbdb_person_b_id=row["cbdb_person_b_id"],
        candidate_strength=str(row["candidate_strength"]),
        candidate_basis=str(row["candidate_basis"]),
        relation_label=row["relation_label"],
        source_work_id=row["source_work_id"],
        pages=row["pages"],
        review_status=str(row["review_status"]),
        person_a_id=_uuid_or_none(row.get("person_a_id")),
        person_b_id=_uuid_or_none(row.get("person_b_id")),
    )


def _uuid_or_none(value: object) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
