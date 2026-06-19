from figure_data.db.base import Base


def test_ai_job_events_table_exists() -> None:
    table = Base.metadata.tables["figure_data.ai_job_events"]

    assert table.schema == "figure_data"
    assert "id" in table.c
    assert "job_id" in table.c
    assert "event_type" in table.c
    assert "actor" in table.c
    assert "message" in table.c
    assert "metadata_json" in table.c
    assert "created_at" in table.c


def test_ai_job_events_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_job_events"]
    index_names = {index.name for index in table.indexes}

    assert "ix_figure_data_ai_job_events_job_created_at" in index_names
    assert "ix_figure_data_ai_job_events_event_type_created_at" in index_names
