"""create encounter review tables

Revision ID: 20260608_0001
Revises: 20260604_0001
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260608_0001"
down_revision: str | None = "20260604_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table("encounters",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("person_a_id", _uuid(), nullable=False),
        sa.Column("person_b_id", _uuid(), nullable=False),
        sa.Column("person_a_cbdb_id", sa.Integer(), nullable=True),
        sa.Column("person_b_cbdb_id", sa.Integer(), nullable=True),
        sa.Column("encounter_kind", sa.String(length=64), nullable=False),
        sa.Column("certainty_level", sa.String(length=32), nullable=False),
        sa.Column("path_eligible", sa.Boolean(), nullable=False),
        sa.Column("time_start_year", sa.Integer(), nullable=True),
        sa.Column("time_end_year", sa.Integer(), nullable=True),
        sa.Column("source_work_id", sa.Integer(), nullable=True),
        sa.Column("pages", sa.Text(), nullable=True),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("person_a_id <> person_b_id", name="ck_encounters_distinct_people"),
        sa.ForeignKeyConstraint(
            ["person_a_id"],
            ["figure_data.persons.id"],
            name="fk_encounters_person_a_id_persons",
        ),
        sa.ForeignKeyConstraint(
            ["person_b_id"],
            ["figure_data.persons.id"],
            name="fk_encounters_person_b_id_persons",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_encounters"),
        sa.UniqueConstraint(
            "person_a_id",
            "person_b_id",
            "encounter_kind",
            "time_start_year",
            "time_end_year",
            "source_work_id",
            "pages",
            name="uq_encounters_pair_kind_time_source",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_encounters_person_a_id",
        "encounters",
        ["person_a_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_encounters_person_b_id",
        "encounters",
        ["person_b_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_encounters_path_eligible",
        "encounters",
        ["path_eligible"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_encounters_status",
        "encounters",
        ["status"],
        schema=SCHEMA,
    )
    op.create_table("encounter_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("encounter_id", _uuid(), nullable=False),
        sa.Column("candidate_table", sa.String(length=64), nullable=True),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("source_ref_id", sa.Integer(), nullable=True),
        sa.Column("source_work_id", sa.Integer(), nullable=True),
        sa.Column("pages", sa.Text(), nullable=True),
        sa.Column("evidence_kind", sa.String(length=64), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("raw_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["encounter_id"],
            ["figure_data.encounters.id"],
            name="fk_encounter_evidence_encounter_id_encounters",
        ),
        sa.ForeignKeyConstraint(
            ["source_ref_id"],
            ["figure_data.source_refs.id"],
            name="fk_encounter_evidence_source_ref_id_source_refs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_encounter_evidence"),
        sa.UniqueConstraint(
            "encounter_id",
            "candidate_table",
            "candidate_id",
            name="uq_encounter_evidence_candidate",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_encounter_evidence_encounter_id",
        "encounter_evidence",
        ["encounter_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_encounter_evidence_candidate",
        "encounter_evidence",
        ["candidate_table", "candidate_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_figure_data_encounter_evidence_candidate",
        table_name="encounter_evidence",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_encounter_evidence_encounter_id",
        table_name="encounter_evidence",
        schema=SCHEMA,
    )
    op.drop_table("encounter_evidence", schema=SCHEMA)
    op.drop_index(
        "ix_figure_data_encounters_status",
        table_name="encounters",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_encounters_path_eligible",
        table_name="encounters",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_encounters_person_b_id",
        table_name="encounters",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_figure_data_encounters_person_a_id",
        table_name="encounters",
        schema=SCHEMA,
    )
    op.drop_table("encounters", schema=SCHEMA)
