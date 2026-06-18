"""create AI generation jobs

Revision ID: 20260618_0001
Revises: 20260613_0004
Create Date: 2026-06-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260618_0001"
down_revision: str | None = "20260613_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table("ai_generation_jobs",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_kind", sa.Text(), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("result_ref_type", sa.Text(), nullable=True),
        sa.Column("result_ref_id", _uuid(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "job_type in ('candidate_review_suggestion')",
            name=op.f("ck_ai_generation_jobs_job_type"),
        ),
        sa.CheckConstraint(
            "target_type in ('candidate')",
            name=op.f("ck_ai_generation_jobs_target_type"),
        ),
        sa.CheckConstraint(
            "target_kind in ('relationship', 'kinship')",
            name=op.f("ck_ai_generation_jobs_target_kind"),
        ),
        sa.CheckConstraint(
            "status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name=op.f("ck_ai_generation_jobs_status"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_generation_jobs"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_generation_jobs_status_created_at",
        "ai_generation_jobs",
        ["status", "created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_generation_jobs_target",
        "ai_generation_jobs",
        ["target_type", "target_kind", "target_id", "created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_generation_jobs_job_type_created_at",
        "ai_generation_jobs",
        ["job_type", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_figure_data_ai_generation_jobs_job_type_created_at",
        table_name="ai_generation_jobs",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_generation_jobs_target",
        table_name="ai_generation_jobs",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_generation_jobs_status_created_at",
        table_name="ai_generation_jobs",
        schema=SCHEMA,
    )
    op.drop_table("ai_generation_jobs", schema=SCHEMA)
