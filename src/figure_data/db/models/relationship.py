from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base
from figure_data.db.models.mixins import ImportedRowMixin


class AssociationCode(ImportedRowMixin, Base):
    __tablename__ = "association_codes"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    association_code: Mapped[int | None] = mapped_column(Integer)
    label_zh: Mapped[str | None] = mapped_column(Text)
    label_en: Mapped[str | None] = mapped_column(Text)
    role_type: Mapped[str | None] = mapped_column(Text)
    association_type_codes: Mapped[list[int] | None] = mapped_column(JSONB)
    association_type_labels: Mapped[list[str] | None] = mapped_column(JSONB)
    examples: Mapped[list[str] | None] = mapped_column(JSONB)


class RelationshipCandidate(ImportedRowMixin, Base):
    __tablename__ = "relationship_candidates"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_a_id: Mapped[UUID | None] = mapped_column(ForeignKey("figure_data.persons.id"))
    person_b_id: Mapped[UUID | None] = mapped_column(ForeignKey("figure_data.persons.id"))
    cbdb_person_a_id: Mapped[int | None] = mapped_column(Integer)
    cbdb_person_b_id: Mapped[int | None] = mapped_column(Integer)
    association_code: Mapped[int | None] = mapped_column(Integer)
    association_label: Mapped[str | None] = mapped_column(Text)
    first_year: Mapped[int | None] = mapped_column(Integer)
    last_year: Mapped[int | None] = mapped_column(Integer)
    source_work_id: Mapped[int | None] = mapped_column(Integer)
    pages: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    candidate_strength: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_basis: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unreviewed")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    review_note: Mapped[str | None] = mapped_column(Text)
    promoted_encounter_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))


class KinshipCode(ImportedRowMixin, Base):
    __tablename__ = "kinship_codes"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kinship_code: Mapped[int | None] = mapped_column(Integer)
    label_zh: Mapped[str | None] = mapped_column(Text)
    label_en: Mapped[str | None] = mapped_column(Text)
    kinship_path: Mapped[str | None] = mapped_column(Text)
    upstep: Mapped[int | None] = mapped_column(Integer)
    downstep: Mapped[int | None] = mapped_column(Integer)
    marstep: Mapped[int | None] = mapped_column(Integer)


class KinshipCandidate(ImportedRowMixin, Base):
    __tablename__ = "kinship_candidates"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_a_id: Mapped[UUID | None] = mapped_column(ForeignKey("figure_data.persons.id"))
    person_b_id: Mapped[UUID | None] = mapped_column(ForeignKey("figure_data.persons.id"))
    kinship_code: Mapped[int | None] = mapped_column(Integer)
    kinship_label_zh: Mapped[str | None] = mapped_column(Text)
    kinship_label_en: Mapped[str | None] = mapped_column(Text)
    kinship_path: Mapped[str | None] = mapped_column(Text)
    upstep: Mapped[int | None] = mapped_column(Integer)
    downstep: Mapped[int | None] = mapped_column(Integer)
    marstep: Mapped[int | None] = mapped_column(Integer)
    source_work_id: Mapped[int | None] = mapped_column(Integer)
    pages: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    candidate_strength: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_basis: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unreviewed")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    review_note: Mapped[str | None] = mapped_column(Text)
    promoted_encounter_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
