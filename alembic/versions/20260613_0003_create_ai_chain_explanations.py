"""create AI chain explanations table

Revision ID: 20260613_0003
Revises: 20260613_0002
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260613_0003"
down_revision: str | None = "20260613_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table("ai_chain_explanations",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("ai_run_id", _uuid(), nullable=False),
        sa.Column("chain_hash", sa.Text(), nullable=False),
        sa.Column("source_person_id", _uuid(), nullable=False),
        sa.Column("target_person_id", _uuid(), nullable=False),
        sa.Column("max_depth", sa.Integer(), nullable=False),
        sa.Column("encounter_ids", postgresql.JSONB(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("edge_explanations", postgresql.JSONB(), nullable=False),
        sa.Column("source_ref_ids", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('generated', 'archived')",
            name=op.f("ck_ai_chain_explanations_status"),
        ),
        sa.CheckConstraint(
            "max_depth >= 1 and max_depth <= 30",
            name=op.f("ck_ai_chain_explanations_max_depth"),
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["figure_data.ai_runs.id"],
            name="fk_ai_chain_explanations_ai_run_id_ai_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_chain_explanations"),
        sa.UniqueConstraint("chain_hash", name="uq_ai_chain_explanations_chain_hash"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_chain_explanations_source_target",
        "ai_chain_explanations",
        ["source_person_id", "target_person_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_chain_explanations_ai_run_id",
        "ai_chain_explanations",
        ["ai_run_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_chain_explanations_status",
        "ai_chain_explanations",
        ["status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_chain_explanations_created_at",
        "ai_chain_explanations",
        ["created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_figure_data_ai_chain_explanations_created_at",
        table_name="ai_chain_explanations",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_chain_explanations_status",
        table_name="ai_chain_explanations",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_chain_explanations_ai_run_id",
        table_name="ai_chain_explanations",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_chain_explanations_source_target",
        table_name="ai_chain_explanations",
        schema=SCHEMA,
    )
    op.drop_table("ai_chain_explanations", schema=SCHEMA)
