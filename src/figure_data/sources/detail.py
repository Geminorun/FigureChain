from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from figure_data.sources.types import (
    LinkedEncounterEvidence,
    SourceRefDetail,
    SourceWorkDetail,
)


class SourceWorkNotFoundError(ValueError):
    """Raised when a source work cannot be found."""


class SourceRefNotFoundError(ValueError):
    """Raised when a source ref cannot be found."""


SOURCE_WORK_DETAIL_SQL = """
select
  sw.id as source_work_id,
  sw.text_code,
  sw.title_zh,
  sw.title_en,
  sw.source_name,
  sw.source_table,
  sw.source_pk,
  count(distinct sr.id) as ref_count,
  count(distinct ee.encounter_id) as encounter_count
from figure_data.source_works sw
left join figure_data.source_refs sr on sr.source_work_id = sw.id
left join figure_data.encounter_evidence ee on ee.source_work_id = sw.id
where sw.id = :source_work_id
group by sw.id
"""

SOURCE_REF_DETAIL_SQL = """
select
  sr.id as source_ref_id,
  sr.source_work_id,
  sr.ref_source_table,
  sr.ref_source_pk,
  sr.pages,
  sr.notes,
  sr.source_name,
  sr.source_table,
  sr.source_pk
from figure_data.source_refs sr
where sr.id = :source_ref_id
"""

SOURCE_REF_EVIDENCE_SQL = """
select
  ee.id as evidence_id,
  ee.encounter_id,
  ee.evidence_kind,
  ee.evidence_summary,
  ee.pages,
  ee.created_at
from figure_data.encounter_evidence ee
where ee.source_ref_id = :source_ref_id
order by ee.created_at desc, ee.id
"""


def get_source_work_detail(session: Session, source_work_id: int) -> SourceWorkDetail:
    """Return one source work detail or raise SourceWorkNotFoundError."""

    row = (
        session.execute(text(SOURCE_WORK_DETAIL_SQL), {"source_work_id": source_work_id})
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise SourceWorkNotFoundError(f"source work was not found: {source_work_id}")
    return _source_work(row)


def get_source_ref_detail(session: Session, source_ref_id: int) -> SourceRefDetail:
    """Return one source ref detail or raise SourceRefNotFoundError."""

    row = (
        session.execute(text(SOURCE_REF_DETAIL_SQL), {"source_ref_id": source_ref_id})
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise SourceRefNotFoundError(f"source ref was not found: {source_ref_id}")

    source_work = None
    if row["source_work_id"] is not None:
        source_work = get_source_work_detail(session, row["source_work_id"])

    evidence_rows = (
        session.execute(text(SOURCE_REF_EVIDENCE_SQL), {"source_ref_id": source_ref_id})
        .mappings()
        .all()
    )
    return SourceRefDetail(
        source_ref_id=row["source_ref_id"],
        source_work=source_work,
        ref_source_table=row["ref_source_table"],
        ref_source_pk=row["ref_source_pk"],
        pages=row["pages"],
        notes=row["notes"],
        source_name=row["source_name"],
        source_table=row["source_table"],
        source_pk=row["source_pk"],
        linked_encounter_evidence=[
            LinkedEncounterEvidence(
                evidence_id=evidence["evidence_id"],
                encounter_id=_uuid(evidence["encounter_id"]),
                evidence_kind=evidence["evidence_kind"],
                evidence_summary=evidence["evidence_summary"],
                pages=evidence["pages"],
                created_at=_datetime(evidence["created_at"]),
            )
            for evidence in evidence_rows
        ],
    )


def _source_work(row: object) -> SourceWorkDetail:
    return SourceWorkDetail(
        source_work_id=row["source_work_id"],  # type: ignore[index]
        text_code=row["text_code"],  # type: ignore[index]
        title_zh=row["title_zh"],  # type: ignore[index]
        title_en=row["title_en"],  # type: ignore[index]
        source_name=row["source_name"],  # type: ignore[index]
        source_table=row["source_table"],  # type: ignore[index]
        source_pk=row["source_pk"],  # type: ignore[index]
        ref_count=row["ref_count"] or 0,  # type: ignore[index]
        encounter_count=row["encounter_count"] or 0,  # type: ignore[index]
    )


def _uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
