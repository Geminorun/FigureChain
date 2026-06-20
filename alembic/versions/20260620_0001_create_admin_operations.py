"""create admin operations

Revision ID: 20260620_0001
Revises: 20260619_0004
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260620_0001"
down_revision: str | None = "20260619_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def upgrade() -> None:
    op.create_table(
        "admin_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_type", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "request_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "result_summary",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("related_resource_type", sa.Text(), nullable=True),
        sa.Column("related_resource_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name=op.f("ck_admin_operations_status"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_admin_operations_status_created_at",
        "admin_operations",
        ["status", "created_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_admin_operations_type_created_at",
        "admin_operations",
        ["operation_type", "created_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_admin_operations_related_resource",
        "admin_operations",
        ["related_resource_type", "related_resource_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.alter_column(
        "admin_operations",
        "request_payload",
        server_default=None,
        schema=SCHEMA,
    )
    op.alter_column(
        "admin_operations",
        "result_summary",
        server_default=None,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_figure_data_admin_operations_related_resource",
        table_name="admin_operations",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_admin_operations_type_created_at",
        table_name="admin_operations",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_admin_operations_status_created_at",
        table_name="admin_operations",
        schema=SCHEMA,
    )
    op.drop_table("admin_operations", schema=SCHEMA)
