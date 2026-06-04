from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base
from figure_data.db.models.mixins import ImportedRowMixin


class OfficeCode(ImportedRowMixin, Base):
    __tablename__ = "office_codes"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    office_code: Mapped[int | None] = mapped_column(Integer)
    label_zh: Mapped[str | None] = mapped_column(Text)
    label_en: Mapped[str | None] = mapped_column(Text)
    office_category_code: Mapped[int | None] = mapped_column(Integer)


class OfficePosting(ImportedRowMixin, Base):
    __tablename__ = "office_postings"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[UUID | None] = mapped_column(ForeignKey("figure_data.persons.id"))
    office_code: Mapped[int | None] = mapped_column(Integer)
    office_label: Mapped[str | None] = mapped_column(Text)
    posting_year: Mapped[int | None] = mapped_column(Integer)
    source_work_id: Mapped[int | None] = mapped_column(Integer)
    pages: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
