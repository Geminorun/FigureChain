from sqlalchemy import Column, MetaData, String, Table
from sqlalchemy.dialects import postgresql

from figure_data.importing.upsert import UpsertStats, build_upsert_statement


def test_upsert_uses_stable_source_identity_and_excludes_review_fields() -> None:
    table = Table(
        "relationship_candidates",
        MetaData(),
        Column("source_name", String),
        Column("source_table", String),
        Column("source_pk", String),
        Column("source_row_hash", String),
        Column("candidate_strength", String),
        Column("review_status", String),
        schema="figure_data",
    )

    statement = build_upsert_statement(
        table,
        [{"source_name": "cbdb", "source_table": "ASSOC_DATA", "source_pk": "c_assoc_id=1"}],
        protected_columns={"review_status"},
    )
    compiled = str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[no-untyped-call]

    assert "ON CONFLICT (source_name, source_table, source_pk)" in compiled
    assert "review_status = excluded.review_status" not in compiled


def test_upsert_statement_returns_insert_marker_for_import_batch_stats() -> None:
    table = Table(
        "persons",
        MetaData(),
        Column("source_name", String),
        Column("source_table", String),
        Column("source_pk", String),
        Column("source_row_hash", String),
        schema="figure_data",
    )

    statement = build_upsert_statement(
        table,
        [
            {
                "source_name": "cbdb",
                "source_table": "BIOG_MAIN",
                "source_pk": "c_personid=1",
                "source_row_hash": "hash",
            }
        ],
    )
    compiled = str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[no-untyped-call]

    assert "RETURNING xmax = 0 AS inserted" in compiled


def test_upsert_stats_accumulates_insert_update_skip_counts() -> None:
    stats = UpsertStats()
    stats.add(UpsertStats(rows_inserted=2, rows_updated=3, rows_skipped=1))

    assert stats.rows_inserted == 2
    assert stats.rows_updated == 3
    assert stats.rows_skipped == 1
