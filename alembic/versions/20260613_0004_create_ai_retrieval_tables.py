"""create AI retrieval tables

Revision ID: 20260613_0004
Revises: 20260613_0003
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260613_0004"
down_revision: str | None = "20260613_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.execute("create extension if not exists vector")
    op.create_table("ai_retrieval_documents",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_pk", sa.Text(), nullable=False),
        sa.Column("source_ref_id", sa.Integer(), nullable=True),
        sa.Column("encounter_evidence_id", sa.Integer(), nullable=True),
        sa.Column("source_work_id", sa.Integer(), nullable=True),
        sa.Column("title_zh", sa.Text(), nullable=True),
        sa.Column("title_en", sa.Text(), nullable=True),
        sa.Column("pages", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_kind in ('source_ref', 'encounter_evidence')",
            name=op.f("ck_ai_retrieval_documents_source_kind"),
        ),
        sa.CheckConstraint(
            "status in ('active', 'stale', 'archived')",
            name=op.f("ck_ai_retrieval_documents_status"),
        ),
        sa.ForeignKeyConstraint(
            ["source_ref_id"],
            ["figure_data.source_refs.id"],
            name="fk_ai_retrieval_documents_source_ref_id_source_refs",
        ),
        sa.ForeignKeyConstraint(
            ["encounter_evidence_id"],
            ["figure_data.encounter_evidence.id"],
            name="fk_ai_retrieval_documents_encounter_evidence_id_encounter_evidence",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_retrieval_documents"),
        sa.UniqueConstraint(
            "source_kind",
            "source_pk",
            "chunk_index",
            "text_hash",
            name="uq_ai_retrieval_documents_source_chunk_hash",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_retrieval_documents_source_ref_id",
        "ai_retrieval_documents",
        ["source_ref_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_retrieval_documents_encounter_evidence_id",
        "ai_retrieval_documents",
        ["encounter_evidence_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_retrieval_documents_status",
        "ai_retrieval_documents",
        ["status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_retrieval_documents_text_hash",
        "ai_retrieval_documents",
        ["text_hash"],
        schema=SCHEMA,
    )
    op.execute(
        """
        create table figure_data.ai_retrieval_embeddings (
            id uuid not null,
            document_id uuid not null,
            provider text not null,
            model_name text not null,
            embedding_dimensions integer not null,
            embedding vector(8) not null,
            text_hash text not null,
            created_at timestamp with time zone not null,
            constraint pk_ai_retrieval_embeddings primary key (id),
            constraint fk_ai_retrieval_embeddings_document_id_ai_retrieval_documents
                foreign key(document_id)
                references figure_data.ai_retrieval_documents (id),
            constraint uq_ai_retrieval_embeddings_document_provider_model
                unique (document_id, provider, model_name)
        )
        """
    )
    op.create_index(
        "ix_figure_data_ai_retrieval_embeddings_document_id",
        "ai_retrieval_embeddings",
        ["document_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_retrieval_embeddings_model",
        "ai_retrieval_embeddings",
        ["provider", "model_name"],
        schema=SCHEMA,
    )
    op.execute(
        """
        create index ix_figure_data_ai_retrieval_embeddings_hnsw
        on figure_data.ai_retrieval_embeddings
        using hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists figure_data.ix_figure_data_ai_retrieval_embeddings_hnsw")
    op.drop_index(
        "ix_figure_data_ai_retrieval_embeddings_model",
        table_name="ai_retrieval_embeddings",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_retrieval_embeddings_document_id",
        table_name="ai_retrieval_embeddings",
        schema=SCHEMA,
    )
    op.drop_table("ai_retrieval_embeddings", schema=SCHEMA)
    op.drop_index(
        "ix_figure_data_ai_retrieval_documents_text_hash",
        table_name="ai_retrieval_documents",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_retrieval_documents_status",
        table_name="ai_retrieval_documents",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_retrieval_documents_encounter_evidence_id",
        table_name="ai_retrieval_documents",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_retrieval_documents_source_ref_id",
        table_name="ai_retrieval_documents",
        schema=SCHEMA,
    )
    op.drop_table("ai_retrieval_documents", schema=SCHEMA)
