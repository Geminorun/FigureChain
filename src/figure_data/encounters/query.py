from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.encounters.types import (
    EncounterDetail,
    EncounterEvidenceDetail,
    EncounterOperationError,
    EncounterSummary,
)
from figure_data.review.types import CandidatePerson, CandidateSourceRef
from figure_data.search.person_search import search_people


@dataclass(frozen=True)
class EncounterListFilters:
    person_query: str | None = None
    status: str | None = None
    path_eligible: bool | None = None
    limit: int = 20


def list_encounters(session: Session, filters: EncounterListFilters) -> list[EncounterSummary]:
    person_ids = _resolve_person_ids(session, filters.person_query)
    if filters.person_query is not None and not person_ids:
        return []

    params: dict[str, Any] = {"limit": filters.limit}
    where_sql = _build_where(filters, params, person_ids)
    rows = session.execute(
        text(
            f"""
            select
              e.id as encounter_id,
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
              e.encounter_kind,
              e.certainty_level,
              e.path_eligible,
              e.source_work_id,
              e.pages,
              e.status,
              e.reviewed_by,
              e.reviewed_at
            from figure_data.encounters e
            left join figure_data.persons pa on pa.id = e.person_a_id
            left join figure_data.persons pb on pb.id = e.person_b_id
            {where_sql}
            order by e.path_eligible desc, e.reviewed_at desc, e.id
            limit :limit
            """
        ),
        params,
    ).mappings().all()
    return [_summary_from_row(cast(Mapping[str, Any], row)) for row in rows]


def get_encounter_detail(session: Session, encounter_id: UUID) -> EncounterDetail:
    row = session.execute(
        text(
            """
            select
              e.id as encounter_id,
              e.person_a_id,
              e.person_b_id,
              e.person_a_cbdb_id,
              e.person_b_cbdb_id,
              pa.primary_name_zh_hant as person_a_name_hant,
              pa.primary_name_zh_hans as person_a_name_hans,
              pa.primary_name_romanized as person_a_name_romanized,
              pa.birth_year as person_a_birth_year,
              pa.death_year as person_a_death_year,
              array_remove(array_agg(distinct pae.external_id), null) as person_a_external_ids,
              pb.primary_name_zh_hant as person_b_name_hant,
              pb.primary_name_zh_hans as person_b_name_hans,
              pb.primary_name_romanized as person_b_name_romanized,
              pb.birth_year as person_b_birth_year,
              pb.death_year as person_b_death_year,
              array_remove(array_agg(distinct pbe.external_id), null) as person_b_external_ids,
              e.encounter_kind,
              e.certainty_level,
              e.path_eligible,
              e.source_work_id,
              e.pages,
              e.evidence_summary,
              e.review_note,
              e.status,
              e.reviewed_by,
              e.reviewed_at,
              e.created_at,
              e.updated_at
            from figure_data.encounters e
            left join figure_data.persons pa on pa.id = e.person_a_id
            left join figure_data.person_external_ids pae on pae.person_id = pa.id
            left join figure_data.persons pb on pb.id = e.person_b_id
            left join figure_data.person_external_ids pbe on pbe.person_id = pb.id
            where e.id = :encounter_id
            group by e.id, pa.id, pb.id
            """
        ),
        {"encounter_id": encounter_id},
    ).mappings().one_or_none()
    if row is None:
        raise EncounterOperationError(f"encounter not found: {encounter_id}")
    evidence = _load_evidence(session, encounter_id)
    source_refs = _source_refs_from_evidence(session, evidence)
    return _detail_from_row(cast(Mapping[str, Any], row), evidence, source_refs)


def _resolve_person_ids(session: Session, person_query: str | None) -> list[str]:
    if person_query is None or not person_query.strip():
        return []
    return [result.person_id for result in search_people(session, person_query.strip(), limit=20)]


def _build_where(
    filters: EncounterListFilters,
    params: dict[str, Any],
    person_ids: list[str],
) -> str:
    clauses: list[str] = []
    if filters.status:
        clauses.append("e.status = :status")
        params["status"] = filters.status
    if filters.path_eligible is not None:
        clauses.append("e.path_eligible = :path_eligible")
        params["path_eligible"] = filters.path_eligible
    if person_ids:
        clauses.append(
            "(e.person_a_id::text = any(:person_ids) or e.person_b_id::text = any(:person_ids))"
        )
        params["person_ids"] = person_ids
    if not clauses:
        return ""
    return "where " + " and ".join(clauses)


def _load_evidence(session: Session, encounter_id: UUID) -> list[EncounterEvidenceDetail]:
    rows = session.execute(
        text(
            """
            select
              id as evidence_id,
              candidate_table,
              candidate_id,
              source_ref_id,
              source_work_id,
              pages,
              evidence_kind,
              evidence_summary,
              created_at
            from figure_data.encounter_evidence
            where encounter_id = :encounter_id
            order by id
            """
        ),
        {"encounter_id": encounter_id},
    ).mappings().all()
    return [_evidence_from_row(cast(Mapping[str, Any], row)) for row in rows]


def _source_refs_from_evidence(
    session: Session,
    evidence: list[EncounterEvidenceDetail],
) -> list[CandidateSourceRef]:
    source_ref_ids = [item.source_ref_id for item in evidence if item.source_ref_id is not None]
    if not source_ref_ids:
        return []
    rows = session.execute(
        text(
            """
            select
              sr.id as source_ref_id,
              sr.source_work_id,
              sw.title_zh,
              sw.title_en,
              sr.pages,
              sr.notes
            from figure_data.source_refs sr
            left join figure_data.source_works sw on sw.id = sr.source_work_id
            where sr.id = any(:source_ref_ids)
            order by sr.id
            """
        ),
        {"source_ref_ids": source_ref_ids},
    ).mappings().all()
    return [
        CandidateSourceRef(
            source_ref_id=int(row["source_ref_id"]),
            source_work_id=row["source_work_id"],
            title_zh=row["title_zh"],
            title_en=row["title_en"],
            pages=row["pages"],
            notes=row["notes"],
        )
        for row in rows
    ]


def _summary_from_row(row: Mapping[str, Any]) -> EncounterSummary:
    return EncounterSummary(
        encounter_id=row["encounter_id"],
        person_a_name=row["person_a_name"],
        person_b_name=row["person_b_name"],
        encounter_kind=str(row["encounter_kind"]),
        certainty_level=str(row["certainty_level"]),
        path_eligible=bool(row["path_eligible"]),
        source_work_id=row["source_work_id"],
        pages=row["pages"],
        status=str(row["status"]),
        reviewed_by=str(row["reviewed_by"]),
        reviewed_at=row["reviewed_at"],
    )


def _detail_from_row(
    row: Mapping[str, Any],
    evidence: list[EncounterEvidenceDetail],
    source_refs: list[CandidateSourceRef],
) -> EncounterDetail:
    return EncounterDetail(
        encounter_id=row["encounter_id"],
        person_a=_person_from_row(row, prefix="person_a"),
        person_b=_person_from_row(row, prefix="person_b"),
        encounter_kind=str(row["encounter_kind"]),
        certainty_level=str(row["certainty_level"]),
        path_eligible=bool(row["path_eligible"]),
        source_work_id=row["source_work_id"],
        pages=row["pages"],
        evidence_summary=str(row["evidence_summary"]),
        review_note=row["review_note"],
        status=str(row["status"]),
        reviewed_by=str(row["reviewed_by"]),
        reviewed_at=row["reviewed_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        evidence=evidence,
        source_refs=source_refs,
    )


def _person_from_row(row: Mapping[str, Any], *, prefix: str) -> CandidatePerson:
    return CandidatePerson(
        person_id=row[f"{prefix}_id"],
        cbdb_id=row[f"{prefix}_cbdb_id"],
        primary_name_zh_hant=row[f"{prefix}_name_hant"],
        primary_name_zh_hans=row[f"{prefix}_name_hans"],
        primary_name_romanized=row[f"{prefix}_name_romanized"],
        birth_year=row[f"{prefix}_birth_year"],
        death_year=row[f"{prefix}_death_year"],
        external_ids=list(row[f"{prefix}_external_ids"] or []),
    )


def _evidence_from_row(row: Mapping[str, Any]) -> EncounterEvidenceDetail:
    return EncounterEvidenceDetail(
        evidence_id=int(row["evidence_id"]),
        candidate_table=row["candidate_table"],
        candidate_id=row["candidate_id"],
        source_ref_id=row["source_ref_id"],
        source_work_id=row["source_work_id"],
        pages=row["pages"],
        evidence_kind=str(row["evidence_kind"]),
        evidence_summary=str(row["evidence_summary"]),
        created_at=row["created_at"],
    )
