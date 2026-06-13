"""create ai foundation tables

Revision ID: 20260613_0001
Revises: 20260608_0001
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260613_0001"
down_revision: str | None = "20260608_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table("ai_prompt_versions",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("prompt_key", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("output_schema_name", sa.Text(), nullable=False),
        sa.Column("output_schema_version", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('active', 'retired')",
            name=op.f("ck_ai_prompt_versions_status"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_prompt_versions"),
        sa.UniqueConstraint(
            "prompt_key",
            "prompt_version",
            name="uq_ai_prompt_versions_key_version",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_prompt_versions_prompt_key",
        "ai_prompt_versions",
        ["prompt_key"],
        schema=SCHEMA,
    )
    op.create_table("ai_runs",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("prompt_version_id", _uuid(), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("output_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("raw_output_excerpt", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("schema_valid", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status in ('running', 'succeeded', 'failed')",
            name=op.f("ck_ai_runs_status"),
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"],
            ["figure_data.ai_prompt_versions.id"],
            name="fk_ai_runs_prompt_version_id_ai_prompt_versions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_runs"),
        schema=SCHEMA,
    )
    op.create_index("ix_figure_data_ai_runs_status", "ai_runs", ["status"], schema=SCHEMA)
    op.create_index("ix_figure_data_ai_runs_purpose", "ai_runs", ["purpose"], schema=SCHEMA)
    op.create_index(
        "ix_figure_data_ai_runs_prompt_version_id",
        "ai_runs",
        ["prompt_version_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_runs_input_hash",
        "ai_runs",
        ["input_hash"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_figure_data_ai_runs_input_hash", table_name="ai_runs", schema=SCHEMA)
    op.drop_index(
        "ix_figure_data_ai_runs_prompt_version_id",
        table_name="ai_runs",
        schema=SCHEMA,
    )
    op.drop_index("ix_figure_data_ai_runs_purpose", table_name="ai_runs", schema=SCHEMA)
    op.drop_index("ix_figure_data_ai_runs_status", table_name="ai_runs", schema=SCHEMA)
    op.drop_table("ai_runs", schema=SCHEMA)
    op.drop_index(
        "ix_figure_data_ai_prompt_versions_prompt_key",
        table_name="ai_prompt_versions",
        schema=SCHEMA,
    )
    op.drop_table("ai_prompt_versions", schema=SCHEMA)
