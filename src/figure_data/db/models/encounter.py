from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base


class Encounter(Base):
    __tablename__ = "encounters"
    __table_args__ = (
        CheckConstraint("person_a_id <> person_b_id", name="distinct_people"),
        UniqueConstraint(
            "person_a_id",
            "person_b_id",
            "encounter_kind",
            "time_start_year",
            "time_end_year",
            "source_work_id",
            "pages",
            name="uq_encounters_pair_kind_time_source",
        ),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    person_a_id: Mapped[UUID] = mapped_column(ForeignKey("figure_data.persons.id"), nullable=False)
    person_b_id: Mapped[UUID] = mapped_column(ForeignKey("figure_data.persons.id"), nullable=False)
    person_a_cbdb_id: Mapped[int | None] = mapped_column(Integer)
    person_b_cbdb_id: Mapped[int | None] = mapped_column(Integer)
    encounter_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    certainty_level: Mapped[str] = mapped_column(String(32), nullable=False)
    path_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_start_year: Mapped[int | None] = mapped_column(Integer)
    time_end_year: Mapped[int | None] = mapped_column(Integer)
    source_work_id: Mapped[int | None] = mapped_column(Integer)
    pages: Mapped[str | None] = mapped_column(Text)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    review_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_by: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EncounterEvidence(Base):
    __tablename__ = "encounter_evidence"
    __table_args__ = (
        UniqueConstraint(
            "encounter_id",
            "candidate_table",
            "candidate_id",
            name="uq_encounter_evidence_candidate",
        ),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    encounter_id: Mapped[UUID] = mapped_column(
        ForeignKey("figure_data.encounters.id"),
        nullable=False,
    )
    candidate_table: Mapped[str | None] = mapped_column(String(64))
    candidate_id: Mapped[int | None] = mapped_column(Integer)
    source_ref_id: Mapped[int | None] = mapped_column(ForeignKey("figure_data.source_refs.id"))
    source_work_id: Mapped[int | None] = mapped_column(Integer)
    pages: Mapped[str | None] = mapped_column(Text)
    evidence_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
