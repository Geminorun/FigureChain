from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base
from figure_data.db.models.mixins import ImportedRowMixin


class Dynasty(ImportedRowMixin, Base):
    __tablename__ = "dynasties"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dynasty_code: Mapped[int | None] = mapped_column(Integer)
    label_zh: Mapped[str | None] = mapped_column(Text)
    label_en: Mapped[str | None] = mapped_column(Text)


class SourceWork(ImportedRowMixin, Base):
    __tablename__ = "source_works"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    text_code: Mapped[int | None] = mapped_column(Integer)
    title_zh: Mapped[str | None] = mapped_column(Text)
    title_en: Mapped[str | None] = mapped_column(Text)


class SourceRef(ImportedRowMixin, Base):
    __tablename__ = "source_refs"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_work_id: Mapped[int | None] = mapped_column(Integer)
    ref_source_table: Mapped[str] = mapped_column(String(128), nullable=False)
    ref_source_pk: Mapped[str] = mapped_column(Text, nullable=False)
    pages: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
