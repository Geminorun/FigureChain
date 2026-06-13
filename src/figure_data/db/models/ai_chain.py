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


class AIChainExplanation(Base):
    __tablename__ = "ai_chain_explanations"
    __table_args__ = (
        CheckConstraint(
            "status in ('generated', 'archived')",
            name=conv("ck_ai_chain_explanations_status"),
        ),
        CheckConstraint(
            "max_depth >= 1 and max_depth <= 30",
            name=conv("ck_ai_chain_explanations_max_depth"),
        ),
        UniqueConstraint("chain_hash", name="uq_ai_chain_explanations_chain_hash"),
        Index(
            "ix_figure_data_ai_chain_explanations_source_target",
            "source_person_id",
            "target_person_id",
        ),
        Index("ix_figure_data_ai_chain_explanations_ai_run_id", "ai_run_id"),
        Index("ix_figure_data_ai_chain_explanations_status", "status"),
        Index("ix_figure_data_ai_chain_explanations_created_at", "created_at"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    ai_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("figure_data.ai_runs.id"),
        nullable=False,
    )
    chain_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_person_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    target_person_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    max_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    encounter_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    edge_explanations: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    source_ref_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
