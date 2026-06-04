"""create figure_data schema

Revision ID: 20260604_0001
Revises:
Create Date: 2026-06-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260604_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "figure_data"


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def _import_columns() -> list[sa.Column]:
    return [
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_snapshot", sa.String(length=128), nullable=False),
        sa.Column("source_table", sa.String(length=128), nullable=False),
        sa.Column("source_pk", sa.Text(), nullable=False),
        sa.Column("source_row_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_cbdb", postgresql.JSONB(), nullable=False),
        sa.Column(
            "import_batch_id",
            _uuid(),
            sa.ForeignKey("figure_data.import_batches.id"),
            nullable=False,
        ),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _source_identity_constraint(table_name: str) -> sa.UniqueConstraint:
    return sa.UniqueConstraint(
        "source_name",
        "source_table",
        "source_pk",
        name=f"uq_{table_name}_source_name",
    )


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.create_table(
        "import_batches",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_snapshot", sa.String(length=128), nullable=False),
        sa.Column("sqlite_filename", sa.Text(), nullable=False),
        sa.Column("sqlite_sha256", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rows_read", sa.Integer(), nullable=False),
        sa.Column("rows_inserted", sa.Integer(), nullable=False),
        sa.Column("rows_updated", sa.Integer(), nullable=False),
        sa.Column("rows_skipped", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_import_batches"),
        schema=SCHEMA,
    )
    op.create_table(
        "office_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("office_code", sa.Integer(), nullable=True),
        sa.Column("label_zh", sa.Text(), nullable=True),
        sa.Column("label_en", sa.Text(), nullable=True),
        sa.Column("office_category_code", sa.Integer(), nullable=True),
        *_import_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_office_codes"),
        _source_identity_constraint("office_codes"),
        schema=SCHEMA,
    )
    op.create_table(
        "persons",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("primary_name_zh_hant", sa.Text(), nullable=True),
        sa.Column("primary_name_zh_hans", sa.Text(), nullable=True),
        sa.Column("primary_name_romanized", sa.Text(), nullable=True),
        sa.Column("search_name", sa.Text(), nullable=True),
        sa.Column("surname_zh_hant", sa.Text(), nullable=True),
        sa.Column("surname_zh_hans", sa.Text(), nullable=True),
        sa.Column("given_name_zh_hant", sa.Text(), nullable=True),
        sa.Column("given_name_zh_hans", sa.Text(), nullable=True),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("death_year", sa.Integer(), nullable=True),
        sa.Column("index_year", sa.Integer(), nullable=True),
        sa.Column("floruit_start_year", sa.Integer(), nullable=True),
        sa.Column("floruit_end_year", sa.Integer(), nullable=True),
        sa.Column("dynasty_code", sa.Integer(), nullable=True),
        sa.Column("is_female", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_import_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_persons"),
        _source_identity_constraint("persons"),
        schema=SCHEMA,
    )
    op.create_index("ix_figure_data_persons_search_name", "persons", ["search_name"], schema=SCHEMA)
    op.create_table(
        "association_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("association_code", sa.Integer(), nullable=True),
        sa.Column("label_zh", sa.Text(), nullable=True),
        sa.Column("label_en", sa.Text(), nullable=True),
        sa.Column("role_type", sa.Text(), nullable=True),
        sa.Column("association_type_codes", postgresql.JSONB(), nullable=True),
        sa.Column("association_type_labels", postgresql.JSONB(), nullable=True),
        sa.Column("examples", postgresql.JSONB(), nullable=True),
        *_import_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_association_codes"),
        _source_identity_constraint("association_codes"),
        schema=SCHEMA,
    )
    op.create_table(
        "kinship_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kinship_code", sa.Integer(), nullable=True),
        sa.Column("label_zh", sa.Text(), nullable=True),
        sa.Column("label_en", sa.Text(), nullable=True),
        sa.Column("kinship_path", sa.Text(), nullable=True),
        sa.Column("upstep", sa.Integer(), nullable=True),
        sa.Column("downstep", sa.Integer(), nullable=True),
        sa.Column("marstep", sa.Integer(), nullable=True),
        *_import_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_kinship_codes"),
        _source_identity_constraint("kinship_codes"),
        schema=SCHEMA,
    )
    op.create_table(
        "dynasties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dynasty_code", sa.Integer(), nullable=True),
        sa.Column("label_zh", sa.Text(), nullable=True),
        sa.Column("label_en", sa.Text(), nullable=True),
        *_import_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_dynasties"),
        _source_identity_constraint("dynasties"),
        schema=SCHEMA,
    )
    op.create_table(
        "source_works",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("text_code", sa.Integer(), nullable=True),
        sa.Column("title_zh", sa.Text(), nullable=True),
        sa.Column("title_en", sa.Text(), nullable=True),
        *_import_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_source_works"),
        _source_identity_constraint("source_works"),
        schema=SCHEMA,
    )
    op.create_table(
        "source_refs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_work_id", sa.Integer(), nullable=True),
        sa.Column("ref_source_table", sa.String(length=128), nullable=False),
        sa.Column("ref_source_pk", sa.Text(), nullable=False),
        sa.Column("pages", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_import_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_source_refs"),
        _source_identity_constraint("source_refs"),
        schema=SCHEMA,
    )
    op.create_table(
        "person_merge_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_a_id", _uuid(), nullable=False),
        sa.Column("person_b_id", _uuid(), nullable=False),
        sa.Column("candidate_reason", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["person_a_id"],
            ["figure_data.persons.id"],
            name="fk_person_merge_candidates_person_a_id_persons",
        ),
        sa.ForeignKeyConstraint(
            ["person_b_id"],
            ["figure_data.persons.id"],
            name="fk_person_merge_candidates_person_b_id_persons",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_person_merge_candidates"),
        sa.UniqueConstraint(
            "person_a_id",
            "person_b_id",
            name="uq_person_merge_candidates_person_a_id",
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "person_identity_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", _uuid(), nullable=False),
        sa.Column("external_source_name", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.Text(), nullable=True),
        sa.Column("link_note", sa.Text(), nullable=True),
        sa.Column("supersedes_person_id", _uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["figure_data.persons.id"],
            name="fk_person_identity_links_person_id_persons",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_person_identity_links"),
        sa.UniqueConstraint(
            "person_id",
            "external_source_name",
            "external_id",
            name="uq_person_identity_links_person_id",
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "office_postings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", _uuid(), nullable=True),
        sa.Column("office_code", sa.Integer(), nullable=True),
        sa.Column("office_label", sa.Text(), nullable=True),
        sa.Column("posting_year", sa.Integer(), nullable=True),
        sa.Column("source_work_id", sa.Integer(), nullable=True),
        sa.Column("pages", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_import_columns(),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["figure_data.persons.id"],
            name="fk_office_postings_person_id_persons",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_office_postings"),
        _source_identity_constraint("office_postings"),
        schema=SCHEMA,
    )
    op.create_table(
        "person_external_ids",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", _uuid(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        *_import_columns(),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["figure_data.persons.id"],
            name="fk_person_external_ids_person_id_persons",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_person_external_ids"),
        sa.UniqueConstraint(
            "source_name",
            "external_id",
            name="uq_person_external_ids_source_name",
        ),
        sa.UniqueConstraint(
            "person_id",
            "source_name",
            "external_id",
            name="uq_person_external_ids_person_id",
        ),
        _source_identity_constraint("person_external_ids"),
        schema=SCHEMA,
    )
    op.create_table(
        "person_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", _uuid(), nullable=False),
        sa.Column("alias_zh_hant", sa.Text(), nullable=True),
        sa.Column("alias_zh_hans", sa.Text(), nullable=True),
        sa.Column("alias_romanized", sa.Text(), nullable=True),
        sa.Column("search_name", sa.Text(), nullable=True),
        sa.Column("alias_type_code", sa.Integer(), nullable=True),
        sa.Column("alias_type_label_zh", sa.Text(), nullable=True),
        sa.Column("alias_type_label_en", sa.Text(), nullable=True),
        *_import_columns(),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["figure_data.persons.id"],
            name="fk_person_aliases_person_id_persons",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_person_aliases"),
        _source_identity_constraint("person_aliases"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_figure_data_person_aliases_search_name",
        "person_aliases",
        ["search_name"],
        schema=SCHEMA,
    )
    op.create_table(
        "relationship_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_a_id", _uuid(), nullable=True),
        sa.Column("person_b_id", _uuid(), nullable=True),
        sa.Column("cbdb_person_a_id", sa.Integer(), nullable=True),
        sa.Column("cbdb_person_b_id", sa.Integer(), nullable=True),
        sa.Column("association_code", sa.Integer(), nullable=True),
        sa.Column("association_label", sa.Text(), nullable=True),
        sa.Column("first_year", sa.Integer(), nullable=True),
        sa.Column("last_year", sa.Integer(), nullable=True),
        sa.Column("source_work_id", sa.Integer(), nullable=True),
        sa.Column("pages", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("candidate_strength", sa.String(length=32), nullable=False),
        sa.Column("candidate_basis", sa.String(length=64), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("promoted_encounter_id", _uuid(), nullable=True),
        *_import_columns(),
        sa.ForeignKeyConstraint(
            ["person_a_id"],
            ["figure_data.persons.id"],
            name="fk_relationship_candidates_person_a_id_persons",
        ),
        sa.ForeignKeyConstraint(
            ["person_b_id"],
            ["figure_data.persons.id"],
            name="fk_relationship_candidates_person_b_id_persons",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_relationship_candidates"),
        _source_identity_constraint("relationship_candidates"),
        schema=SCHEMA,
    )
    op.create_table(
        "kinship_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_a_id", _uuid(), nullable=True),
        sa.Column("person_b_id", _uuid(), nullable=True),
        sa.Column("kinship_code", sa.Integer(), nullable=True),
        sa.Column("kinship_label_zh", sa.Text(), nullable=True),
        sa.Column("kinship_label_en", sa.Text(), nullable=True),
        sa.Column("kinship_path", sa.Text(), nullable=True),
        sa.Column("upstep", sa.Integer(), nullable=True),
        sa.Column("downstep", sa.Integer(), nullable=True),
        sa.Column("marstep", sa.Integer(), nullable=True),
        sa.Column("source_work_id", sa.Integer(), nullable=True),
        sa.Column("pages", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("candidate_strength", sa.String(length=32), nullable=False),
        sa.Column("candidate_basis", sa.String(length=64), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("promoted_encounter_id", _uuid(), nullable=True),
        *_import_columns(),
        sa.ForeignKeyConstraint(
            ["person_a_id"],
            ["figure_data.persons.id"],
            name="fk_kinship_candidates_person_a_id_persons",
        ),
        sa.ForeignKeyConstraint(
            ["person_b_id"],
            ["figure_data.persons.id"],
            name="fk_kinship_candidates_person_b_id_persons",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_kinship_candidates"),
        _source_identity_constraint("kinship_candidates"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("kinship_candidates", schema=SCHEMA)
    op.drop_table("relationship_candidates", schema=SCHEMA)
    op.drop_index(
        "ix_figure_data_person_aliases_search_name",
        table_name="person_aliases",
        schema=SCHEMA,
    )
    op.drop_table("person_aliases", schema=SCHEMA)
    op.drop_table("person_external_ids", schema=SCHEMA)
    op.drop_table("office_postings", schema=SCHEMA)
    op.drop_table("person_identity_links", schema=SCHEMA)
    op.drop_table("person_merge_candidates", schema=SCHEMA)
    op.drop_table("source_refs", schema=SCHEMA)
    op.drop_table("source_works", schema=SCHEMA)
    op.drop_table("dynasties", schema=SCHEMA)
    op.drop_table("kinship_codes", schema=SCHEMA)
    op.drop_table("association_codes", schema=SCHEMA)
    op.drop_index("ix_figure_data_persons_search_name", table_name="persons", schema=SCHEMA)
    op.drop_table("persons", schema=SCHEMA)
    op.drop_table("office_codes", schema=SCHEMA)
    op.drop_table("import_batches", schema=SCHEMA)
