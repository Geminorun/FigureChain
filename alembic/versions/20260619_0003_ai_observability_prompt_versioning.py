"""add AI run observability fields

Revision ID: 20260619_0003
Revises: 20260619_0002
Create Date: 2026-06-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260619_0003"
down_revision: str | None = "20260619_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def upgrade() -> None:
    op.add_column(
        "ai_runs",
        sa.Column("provider_request_id", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_runs",
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_runs",
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_runs",
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_runs",
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_runs",
        sa.Column("estimated_cost", sa.Numeric(18, 9), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_runs",
        sa.Column("cost_currency", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_runs",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_runs",
        sa.Column(
            "provider_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema=SCHEMA,
    )
    op.alter_column("ai_runs", "retry_count", server_default=None, schema=SCHEMA)
    op.alter_column("ai_runs", "provider_metadata", server_default=None, schema=SCHEMA)


def downgrade() -> None:
    for column_name in [
        "provider_metadata",
        "retry_count",
        "cost_currency",
        "estimated_cost",
        "total_tokens",
        "completion_tokens",
        "prompt_tokens",
        "latency_ms",
        "provider_request_id",
    ]:
        op.drop_column("ai_runs", column_name, schema=SCHEMA)
