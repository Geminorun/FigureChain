"""create chain share snapshots

Revision ID: 20260619_0001
Revises: 20260618_0001
Create Date: 2026-06-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260619_0001"
down_revision: str | None = "20260618_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table("chain_share_snapshots",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("share_slug", sa.Text(), nullable=False),
        sa.Column("source_person_id", _uuid(), nullable=False),
        sa.Column("target_person_id", _uuid(), nullable=False),
        sa.Column("chain_hash", sa.Text(), nullable=False),
        sa.Column("encounter_ids", postgresql.JSONB(), nullable=False),
        sa.Column("path_payload", postgresql.JSONB(), nullable=False),
        sa.Column("filters_applied", postgresql.JSONB(), nullable=False),
        sa.Column(
            "include_ai_explanation",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "include_rag_context",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_chain_share_snapshots"),
        sa.UniqueConstraint("share_slug", name="uq_chain_share_snapshots_share_slug"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_chain_share_snapshots_chain_hash",
        "chain_share_snapshots",
        ["chain_hash"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_chain_share_snapshots_created_at",
        "chain_share_snapshots",
        ["created_at"],
        schema=SCHEMA,
    )

    op.create_table("chain_export_records",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("share_snapshot_id", _uuid(), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("source_ids", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "format in ('markdown')",
            name=op.f("ck_chain_export_records_format"),
        ),
        sa.ForeignKeyConstraint(
            ["share_snapshot_id"],
            [f"{SCHEMA}.chain_share_snapshots.id"],
            name="fk_chain_export_records_share_snapshot_id_chain_share_snapshots",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chain_export_records"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_chain_export_records_share_snapshot_id",
        "chain_export_records",
        ["share_snapshot_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_figure_data_chain_export_records_share_snapshot_id",
        table_name="chain_export_records",
        schema=SCHEMA,
    )
    op.drop_table("chain_export_records", schema=SCHEMA)
    op.drop_index(
        "ix_figure_data_chain_share_snapshots_created_at",
        table_name="chain_share_snapshots",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_chain_share_snapshots_chain_hash",
        table_name="chain_share_snapshots",
        schema=SCHEMA,
    )
    op.drop_table("chain_share_snapshots", schema=SCHEMA)
