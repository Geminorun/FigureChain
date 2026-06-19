from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from figure_data.db.base import Base


class GraphProjectionBatch(Base):
    __tablename__ = "graph_projection_batches"
    __table_args__ = (
        CheckConstraint(
            "mode in ('rebuild', 'incremental')",
            name=conv("ck_graph_projection_batches_mode"),
        ),
        CheckConstraint(
            "status in ('running', 'succeeded', 'failed')",
            name=conv("ck_graph_projection_batches_status"),
        ),
        Index(
            "ix_figure_data_graph_projection_batches_status_started_at",
            "status",
            "started_at",
        ),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)
    source_watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    encounters_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relationships_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relationships_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    persons_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="not_run",
    )
    validation_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
