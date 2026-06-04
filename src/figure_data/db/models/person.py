from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base
from figure_data.db.models.mixins import ImportedRowMixin


class Person(ImportedRowMixin, Base):
    __tablename__ = "persons"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    primary_name_zh_hant: Mapped[str | None] = mapped_column(Text)
    primary_name_zh_hans: Mapped[str | None] = mapped_column(Text)
    primary_name_romanized: Mapped[str | None] = mapped_column(Text)
    search_name: Mapped[str | None] = mapped_column(Text, index=True)
    surname_zh_hant: Mapped[str | None] = mapped_column(Text)
    surname_zh_hans: Mapped[str | None] = mapped_column(Text)
    given_name_zh_hant: Mapped[str | None] = mapped_column(Text)
    given_name_zh_hans: Mapped[str | None] = mapped_column(Text)
    birth_year: Mapped[int | None] = mapped_column(Integer)
    death_year: Mapped[int | None] = mapped_column(Integer)
    index_year: Mapped[int | None] = mapped_column(Integer)
    floruit_start_year: Mapped[int | None] = mapped_column(Integer)
    floruit_end_year: Mapped[int | None] = mapped_column(Integer)
    dynasty_code: Mapped[int | None] = mapped_column(Integer)
    is_female: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)


class PersonExternalId(ImportedRowMixin, Base):
    __tablename__ = "person_external_ids"
    __table_args__ = (
        UniqueConstraint("source_name", "external_id"),
        UniqueConstraint("person_id", "source_name", "external_id"),
        UniqueConstraint(
            "source_name",
            "source_table",
            "source_pk",
            name="uq_person_external_ids_source_identity",
        ),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[UUID] = mapped_column(ForeignKey("figure_data.persons.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)


class PersonAlias(ImportedRowMixin, Base):
    __tablename__ = "person_aliases"
    __table_args__ = (
        UniqueConstraint("source_name", "source_table", "source_pk"),
        {"schema": "figure_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[UUID] = mapped_column(ForeignKey("figure_data.persons.id"), nullable=False)
    alias_zh_hant: Mapped[str | None] = mapped_column(Text)
    alias_zh_hans: Mapped[str | None] = mapped_column(Text)
    alias_romanized: Mapped[str | None] = mapped_column(Text)
    search_name: Mapped[str | None] = mapped_column(Text, index=True)
    alias_type_code: Mapped[int | None] = mapped_column(Integer)
    alias_type_label_zh: Mapped[str | None] = mapped_column(Text)
    alias_type_label_en: Mapped[str | None] = mapped_column(Text)
