from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from figure_data.db.base import Base


class ChainShareSnapshot(Base):
    __tablename__ = "chain_share_snapshots"
    __table_args__ = (
        UniqueConstraint("share_slug", name=conv("uq_chain_share_snapshots_share_slug")),
        Index("ix_figure_data_chain_share_snapshots_chain_hash", "chain_hash"),
        Index("ix_figure_data_chain_share_snapshots_created_at", "created_at"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    share_slug: Mapped[str] = mapped_column(Text, nullable=False)
    source_person_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    target_person_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    chain_hash: Mapped[str] = mapped_column(Text, nullable=False)
    encounter_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    path_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    filters_applied: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    include_ai_explanation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    include_rag_context: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChainExportRecord(Base):
    __tablename__ = "chain_export_records"
    __table_args__ = (
        CheckConstraint(
            "format in ('markdown')",
            name=conv("ck_chain_export_records_format"),
        ),
        Index(
            "ix_figure_data_chain_export_records_share_snapshot_id",
            "share_snapshot_id",
        ),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    share_snapshot_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "figure_data.chain_share_snapshots.id",
            name="fk_chain_export_records_share_snapshot_id_chain_share_snapshots",
        ),
        nullable=False,
    )
    format: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    source_ids: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
