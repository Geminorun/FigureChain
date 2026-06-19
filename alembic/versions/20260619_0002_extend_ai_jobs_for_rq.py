"""extend AI jobs for Redis RQ

Revision ID: 20260619_0002
Revises: 20260619_0001
Create Date: 2026-06-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260619_0002"
down_revision: str | None = "20260619_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("ai_generation_jobs",
        sa.Column("queue_backend", sa.Text(), nullable=False, server_default="database"),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_generation_jobs",
        sa.Column("queue_name", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_generation_jobs",
        sa.Column("queue_job_id", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_generation_jobs",
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_generation_jobs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_generation_jobs",
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_generation_jobs",
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_generation_jobs",
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_generation_jobs",
        sa.Column("worker_id", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_generation_jobs",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.alter_column(
        "ai_generation_jobs",
        "queue_backend",
        server_default=None,
        schema=SCHEMA,
    )
    op.alter_column(
        "ai_generation_jobs",
        "attempt_count",
        server_default=None,
        schema=SCHEMA,
    )
    op.alter_column(
        "ai_generation_jobs",
        "max_attempts",
        server_default=None,
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_ai_generation_jobs_queue_backend"),
        "ai_generation_jobs",
        "queue_backend in ('database', 'rq')",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_ai_generation_jobs_attempt_count"),
        "ai_generation_jobs",
        "attempt_count >= 0",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_ai_generation_jobs_max_attempts"),
        "ai_generation_jobs",
        "max_attempts >= 1",
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_generation_jobs_queue_backend_status",
        "ai_generation_jobs",
        ["queue_backend", "status", "created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_generation_jobs_next_run_at",
        "ai_generation_jobs",
        ["status", "next_run_at"],
        schema=SCHEMA,
    )

    op.create_table("ai_job_events",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("job_id", _uuid(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            [f"{SCHEMA}.ai_generation_jobs.id"],
            name="fk_ai_job_events_job",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_job_events"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_job_events_job_created_at",
        "ai_job_events",
        ["job_id", "created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_ai_job_events_event_type_created_at",
        "ai_job_events",
        ["event_type", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_figure_data_ai_job_events_event_type_created_at",
        table_name="ai_job_events",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_job_events_job_created_at",
        table_name="ai_job_events",
        schema=SCHEMA,
    )
    op.drop_table("ai_job_events", schema=SCHEMA)
    op.drop_index(
        "ix_figure_data_ai_generation_jobs_next_run_at",
        table_name="ai_generation_jobs",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_ai_generation_jobs_queue_backend_status",
        table_name="ai_generation_jobs",
        schema=SCHEMA,
    )
    op.drop_constraint(
        op.f("ck_ai_generation_jobs_max_attempts"),
        "ai_generation_jobs",
        schema=SCHEMA,
    )
    op.drop_constraint(
        op.f("ck_ai_generation_jobs_attempt_count"),
        "ai_generation_jobs",
        schema=SCHEMA,
    )
    op.drop_constraint(
        op.f("ck_ai_generation_jobs_queue_backend"),
        "ai_generation_jobs",
        schema=SCHEMA,
    )
    for column_name in [
        "heartbeat_at",
        "worker_id",
        "cancel_requested_at",
        "next_run_at",
        "max_attempts",
        "attempt_count",
        "enqueued_at",
        "queue_job_id",
        "queue_name",
        "queue_backend",
    ]:
        op.drop_column("ai_generation_jobs", column_name, schema=SCHEMA)
