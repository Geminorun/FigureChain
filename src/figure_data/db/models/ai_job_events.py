from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base


class AIJobEvent(Base):
    __tablename__ = "ai_job_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id"],
            ["figure_data.ai_generation_jobs.id"],
            name="fk_ai_job_events_job",
            ondelete="CASCADE",
        ),
        Index("ix_figure_data_ai_job_events_job_created_at", "job_id", "created_at"),
        Index(
            "ix_figure_data_ai_job_events_event_type_created_at",
            "event_type",
            "created_at",
        ),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
