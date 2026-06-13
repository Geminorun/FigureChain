"""create AI candidate review suggestions table

Revision ID: 20260613_0002
Revises: 20260613_0001
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260613_0002"
down_revision: str | None = "20260613_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table("ai_candidate_review_suggestions",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("ai_run_id", _uuid(), nullable=False),
        sa.Column("candidate_kind", sa.Text(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("evidence_summary_draft", sa.Text(), nullable=False),
        sa.Column("risk_flags", postgresql.JSONB(), nullable=False),
        sa.Column("supporting_source_ref_ids", postgresql.JSONB(), nullable=False),
        sa.Column("review_questions", postgresql.JSONB(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "candidate_kind in ('relationship', 'kinship')",
            name=op.f("ck_ai_candidate_review_suggestions_kind"),
        ),
        sa.CheckConstraint(
            "suggested_action in ("
            "'promote_candidate', 'needs_human_review', 'reject_duplicate', "
            "'insufficient_evidence', 'not_path_candidate'"
            ")",
            name=op.f("ck_ai_candidate_review_suggestions_action"),
        ),
        sa.CheckConstraint(
            "status in ('generated', 'archived')",
            name=op.f("ck_ai_candidate_review_suggestions_status"),
        ),
        sa.CheckConstraint(
            "priority_score >= 0 and priority_score <= 100",
            name=op.f("ck_ai_candidate_review_suggestions_priority_score"),
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["figure_data.ai_runs.id"],
            name="fk_ai_candidate_review_suggestions_ai_run_id_ai_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_candidate_review_suggestions"),
        sa.UniqueConstraint(
            "ai_run_id",
            "candidate_kind",
            "candidate_id",
            name="uq_ai_candidate_review_suggestions_run_candidate",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_candidate_review_suggestions_candidate",
        "ai_candidate_review_suggestions",
        ["candidate_kind", "candidate_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_candidate_review_suggestions_status",
        "ai_candidate_review_suggestions",
        ["status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_candidate_review_suggestions_action",
        "ai_candidate_review_suggestions",
        ["suggested_action"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_candidate_review_suggestions_created_at",
        "ai_candidate_review_suggestions",
        ["created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_figure_data_ai_candidate_review_suggestions_created_at",
        table_name="ai_candidate_review_suggestions",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_candidate_review_suggestions_action",
        table_name="ai_candidate_review_suggestions",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_candidate_review_suggestions_status",
        table_name="ai_candidate_review_suggestions",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_candidate_review_suggestions_candidate",
        table_name="ai_candidate_review_suggestions",
        schema=SCHEMA,
    )
    op.drop_table("ai_candidate_review_suggestions", schema=SCHEMA)
