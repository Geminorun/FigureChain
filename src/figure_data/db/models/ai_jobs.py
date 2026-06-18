from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from figure_data.db.base import Base


class AIGenerationJob(Base):
    __tablename__ = "ai_generation_jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type in ('candidate_review_suggestion')",
            name=conv("ck_ai_generation_jobs_job_type"),
        ),
        CheckConstraint(
            "target_type in ('candidate')",
            name=conv("ck_ai_generation_jobs_target_type"),
        ),
        CheckConstraint(
            "target_kind in ('relationship', 'kinship')",
            name=conv("ck_ai_generation_jobs_target_kind"),
        ),
        CheckConstraint(
            "status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name=conv("ck_ai_generation_jobs_status"),
        ),
        Index(
            "ix_figure_data_ai_generation_jobs_status_created_at",
            "status",
            "created_at",
        ),
        Index(
            "ix_figure_data_ai_generation_jobs_target",
            "target_type",
            "target_kind",
            "target_id",
            "created_at",
        ),
        Index(
            "ix_figure_data_ai_generation_jobs_job_type_created_at",
            "job_type",
            "created_at",
        ),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_kind: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result_ref_type: Mapped[str | None] = mapped_column(Text)
    result_ref_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
