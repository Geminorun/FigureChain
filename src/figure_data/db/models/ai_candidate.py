from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from figure_data.db.base import Base


class AICandidateReviewSuggestion(Base):
    __tablename__ = "ai_candidate_review_suggestions"
    __table_args__ = (
        CheckConstraint(
            "candidate_kind in ('relationship', 'kinship')",
            name=conv("ck_ai_candidate_review_suggestions_kind"),
        ),
        CheckConstraint(
            "suggested_action in ("
            "'promote_candidate', 'needs_human_review', 'reject_duplicate', "
            "'insufficient_evidence', 'not_path_candidate'"
            ")",
            name=conv("ck_ai_candidate_review_suggestions_action"),
        ),
        CheckConstraint(
            "status in ('generated', 'archived')",
            name=conv("ck_ai_candidate_review_suggestions_status"),
        ),
        CheckConstraint(
            "priority_score >= 0 and priority_score <= 100",
            name=conv("ck_ai_candidate_review_suggestions_priority_score"),
        ),
        UniqueConstraint(
            "ai_run_id",
            "candidate_kind",
            "candidate_id",
            name="uq_ai_candidate_review_suggestions_run_candidate",
        ),
        Index(
            "ix_figure_data_ai_candidate_review_suggestions_candidate",
            "candidate_kind",
            "candidate_id",
        ),
        Index("ix_figure_data_ai_candidate_review_suggestions_status", "status"),
        Index(
            "ix_figure_data_ai_candidate_review_suggestions_action",
            "suggested_action",
        ),
        Index(
            "ix_figure_data_ai_candidate_review_suggestions_created_at",
            "created_at",
        ),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    ai_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("figure_data.ai_runs.id"),
        nullable=False,
    )
    candidate_kind: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_id: Mapped[int] = mapped_column(Integer, nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_summary_draft: Mapped[str] = mapped_column(Text, nullable=False)
    risk_flags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    supporting_source_ref_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    review_questions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
