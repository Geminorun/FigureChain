from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base
from figure_data.db.models.mixins import ImportedRowMixin


class PersonMergeCandidate(ImportedRowMixin, Base):
    __tablename__ = "person_merge_candidates"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_a_id: Mapped[UUID] = mapped_column(ForeignKey("figure_data.persons.id"), nullable=False)
    person_b_id: Mapped[UUID] = mapped_column(ForeignKey("figure_data.persons.id"), nullable=False)
    candidate_reason: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unreviewed")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    review_note: Mapped[str | None] = mapped_column(Text)


class PersonIdentityLink(ImportedRowMixin, Base):
    __tablename__ = "person_identity_links"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[UUID] = mapped_column(ForeignKey("figure_data.persons.id"), nullable=False)
    external_source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[str | None] = mapped_column(Text)
    link_note: Mapped[str | None] = mapped_column(Text)
    supersedes_person_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
