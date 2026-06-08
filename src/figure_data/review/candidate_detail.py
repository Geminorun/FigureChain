from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.review.types import (
    CandidateDetail,
    CandidateKind,
    CandidatePerson,
    CandidateReviewError,
    CandidateSourceRef,
    PromotionReadiness,
)


def get_candidate_detail(
    session: Session,
    kind: CandidateKind,
    candidate_id: int,
) -> CandidateDetail:
    candidate_row = session.execute(
        text(_candidate_detail_sql(kind)),
        {"candidate_id": candidate_id},
    ).mappings().one_or_none()
    if candidate_row is None:
        raise CandidateReviewError(f"candidate not found: {kind.value}:{candidate_id}")
    row = cast(Mapping[str, Any], candidate_row)
    source_refs = _load_source_refs(session, str(row["source_table"]), str(row["source_pk"]))
    detail = _candidate_detail_from_row(kind, row, source_refs)
    return detail


def _candidate_detail_sql(kind: CandidateKind) -> str:
    if kind is CandidateKind.RELATIONSHIP:
        return _relationship_detail_sql()
    return _kinship_detail_sql()


def _relationship_detail_sql() -> str:
    return """
    select
      rc.id as candidate_id,
      rc.person_a_id,
      rc.person_b_id,
      rc.cbdb_person_a_id as person_a_cbdb_id,
      rc.cbdb_person_b_id as person_b_cbdb_id,
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
      rc.candidate_strength,
      rc.candidate_basis,
      rc.association_label as relation_label,
      rc.source_work_id,
      rc.pages,
      rc.notes,
      rc.review_status,
      rc.reviewed_by,
      rc.review_note,
      rc.promoted_encounter_id,
      rc.source_name,
      rc.source_table,
      rc.source_pk
    from figure_data.relationship_candidates rc
    left join figure_data.persons pa on pa.id = rc.person_a_id
    left join figure_data.person_external_ids pae on pae.person_id = pa.id
    left join figure_data.persons pb on pb.id = rc.person_b_id
    left join figure_data.person_external_ids pbe on pbe.person_id = pb.id
    where rc.id = :candidate_id
    group by rc.id, pa.id, pb.id
    """


def _kinship_detail_sql() -> str:
    return """
    select
      kc.id as candidate_id,
      kc.person_a_id,
      kc.person_b_id,
      null::integer as person_a_cbdb_id,
      null::integer as person_b_cbdb_id,
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
      kc.candidate_strength,
      kc.candidate_basis,
      coalesce(kc.kinship_label_zh, kc.kinship_label_en) as relation_label,
      kc.source_work_id,
      kc.pages,
      kc.notes,
      kc.review_status,
      kc.reviewed_by,
      kc.review_note,
      kc.promoted_encounter_id,
      kc.source_name,
      kc.source_table,
      kc.source_pk
    from figure_data.kinship_candidates kc
    left join figure_data.persons pa on pa.id = kc.person_a_id
    left join figure_data.person_external_ids pae on pae.person_id = pa.id
    left join figure_data.persons pb on pb.id = kc.person_b_id
    left join figure_data.person_external_ids pbe on pbe.person_id = pb.id
    where kc.id = :candidate_id
    group by kc.id, pa.id, pb.id
    """


def _load_source_refs(
    session: Session,
    source_table: str,
    source_pk: str,
) -> list[CandidateSourceRef]:
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
            where sr.ref_source_table = :source_table
              and sr.ref_source_pk = :source_pk
            order by sr.source_work_id nulls last, sr.id
            """
        ),
        {"source_table": source_table, "source_pk": source_pk},
    ).mappings().all()
    return [_source_ref_from_row(cast(Mapping[str, Any], row)) for row in rows]


def _candidate_detail_from_row(
    kind: CandidateKind,
    row: Mapping[str, Any],
    source_refs: list[CandidateSourceRef],
) -> CandidateDetail:
    readiness = _assess_default_promotion_readiness(kind, row)
    return CandidateDetail(
        candidate_kind=kind,
        candidate_id=int(row["candidate_id"]),
        person_a=_person_from_row(row, prefix="person_a"),
        person_b=_person_from_row(row, prefix="person_b"),
        candidate_strength=str(row["candidate_strength"]),
        candidate_basis=str(row["candidate_basis"]),
        relation_label=row["relation_label"],
        source_work_id=row["source_work_id"],
        pages=row["pages"],
        notes=row["notes"],
        review_status=str(row["review_status"]),
        reviewed_by=row["reviewed_by"],
        review_note=row["review_note"],
        promoted_encounter_id=row["promoted_encounter_id"],
        source_name=str(row["source_name"]),
        source_table=str(row["source_table"]),
        source_pk=str(row["source_pk"]),
        raw_cbdb_snapshot={
            "source_name": row["source_name"],
            "source_table": row["source_table"],
            "source_pk": row["source_pk"],
            "relation_label": row["relation_label"],
            "source_work_id": row["source_work_id"],
            "pages": row["pages"],
            "notes": row["notes"],
        },
        source_refs=source_refs,
        promotion_readiness=readiness,
    )


def _person_from_row(row: Mapping[str, Any], *, prefix: str) -> CandidatePerson:
    person_id = row[f"{prefix}_id"]
    return CandidatePerson(
        person_id=person_id if isinstance(person_id, UUID) or person_id is None else UUID(str(person_id)),
        cbdb_id=row[f"{prefix}_cbdb_id"],
        primary_name_zh_hant=row[f"{prefix}_name_hant"],
        primary_name_zh_hans=row[f"{prefix}_name_hans"],
        primary_name_romanized=row[f"{prefix}_name_romanized"],
        birth_year=row[f"{prefix}_birth_year"],
        death_year=row[f"{prefix}_death_year"],
        external_ids=list(row[f"{prefix}_external_ids"] or []),
    )


def _source_ref_from_row(row: Mapping[str, Any]) -> CandidateSourceRef:
    return CandidateSourceRef(
        source_ref_id=int(row["source_ref_id"]),
        source_work_id=row["source_work_id"],
        title_zh=row["title_zh"],
        title_en=row["title_en"],
        pages=row["pages"],
        notes=row["notes"],
    )


def _assess_default_promotion_readiness(
    kind: CandidateKind,
    row: Mapping[str, Any],
) -> PromotionReadiness:
    reasons: list[str] = []
    if row["person_a_id"] is None or row["person_b_id"] is None:
        reasons.append("missing_person_id")
    if row["person_a_id"] is not None and row["person_a_id"] == row["person_b_id"]:
        reasons.append("self_loop")
    if kind is not CandidateKind.RELATIONSHIP:
        reasons.append("kind_requires_explicit_confirmation")
    if row["candidate_strength"] != "high":
        reasons.append("strength_is_not_high")
    if row["candidate_basis"] != "direct_interaction_likely":
        reasons.append("basis_is_not_direct_interaction_likely")
    if row["review_status"] == "promoted_to_encounter":
        reasons.append("already_promoted")

    default_promotable = len(reasons) == 0
    return PromotionReadiness(
        default_promotable=default_promotable,
        default_path_eligible=default_promotable,
        reasons=reasons,
    )
