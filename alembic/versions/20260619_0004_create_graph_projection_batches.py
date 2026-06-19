"""create graph projection batches

Revision ID: 20260619_0004
Revises: 20260619_0003
Create Date: 2026-06-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260619_0004"
down_revision: str | None = "20260619_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def upgrade() -> None:
    op.create_table(
        "graph_projection_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("triggered_by", sa.Text(), nullable=False),
        sa.Column("source_watermark", sa.DateTime(timezone=True), nullable=True),
        sa.Column("encounters_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "relationships_written",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "relationships_deleted",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("persons_written", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "validation_status",
            sa.Text(),
            nullable=False,
            server_default="not_run",
        ),
        sa.Column(
            "validation_summary",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "mode in ('rebuild', 'incremental')",
            name=op.f("ck_graph_projection_batches_mode"),
        ),
        sa.CheckConstraint(
            "status in ('running', 'succeeded', 'failed')",
            name=op.f("ck_graph_projection_batches_status"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_graph_projection_batches_status_started_at",
        "graph_projection_batches",
        ["status", "started_at"],
        unique=False,
        schema=SCHEMA,
    )
    for column_name in [
        "encounters_seen",
        "relationships_written",
        "relationships_deleted",
        "persons_written",
        "validation_status",
        "validation_summary",
    ]:
        op.alter_column(
            "graph_projection_batches",
            column_name,
            server_default=None,
            schema=SCHEMA,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_figure_data_graph_projection_batches_status_started_at",
        table_name="graph_projection_batches",
        schema=SCHEMA,
    )
    op.drop_table("graph_projection_batches", schema=SCHEMA)
