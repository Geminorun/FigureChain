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
from figure_data.db.vector import PgVector


class AIRetrievalDocument(Base):
    __tablename__ = "ai_retrieval_documents"
    __table_args__ = (
        CheckConstraint(
            "source_kind in ('source_ref', 'encounter_evidence')",
            name=conv("ck_ai_retrieval_documents_source_kind"),
        ),
        CheckConstraint(
            "status in ('active', 'stale', 'archived')",
            name=conv("ck_ai_retrieval_documents_status"),
        ),
        UniqueConstraint(
            "source_kind",
            "source_pk",
            "chunk_index",
            "text_hash",
            name="uq_ai_retrieval_documents_source_chunk_hash",
        ),
        Index("ix_figure_data_ai_retrieval_documents_source_ref_id", "source_ref_id"),
        Index(
            "ix_figure_data_ai_retrieval_documents_encounter_evidence_id",
            "encounter_evidence_id",
        ),
        Index("ix_figure_data_ai_retrieval_documents_status", "status"),
        Index("ix_figure_data_ai_retrieval_documents_text_hash", "text_hash"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_pk: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref_id: Mapped[int | None] = mapped_column(ForeignKey("figure_data.source_refs.id"))
    encounter_evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("figure_data.encounter_evidence.id"),
    )
    source_work_id: Mapped[int | None] = mapped_column(Integer)
    title_zh: Mapped[str | None] = mapped_column(Text)
    title_en: Mapped[str | None] = mapped_column(Text)
    pages: Mapped[str | None] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AIRetrievalEmbedding(Base):
    __tablename__ = "ai_retrieval_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "provider",
            "model_name",
            name="uq_ai_retrieval_embeddings_document_provider_model",
        ),
        Index("ix_figure_data_ai_retrieval_embeddings_document_id", "document_id"),
        Index("ix_figure_data_ai_retrieval_embeddings_model", "provider", "model_name"),
        {"schema": "figure_data"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("figure_data.ai_retrieval_documents.id"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[object] = mapped_column(PgVector(8), nullable=False)
    text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
