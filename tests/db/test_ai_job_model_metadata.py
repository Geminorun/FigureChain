from sqlalchemy import CheckConstraint

from figure_data.db.base import Base
from figure_data.db.enums import AIJobStatus, AIJobTargetKind, AIJobTargetType, AIJobType
from figure_data.db.models import ai_jobs


def test_ai_job_enums_define_initial_values() -> None:
    assert AIJobType.CANDIDATE_REVIEW_SUGGESTION.value == "candidate_review_suggestion"
    assert AIJobTargetType.CANDIDATE.value == "candidate"
    assert AIJobTargetKind.RELATIONSHIP.value == "relationship"
    assert AIJobTargetKind.KINSHIP.value == "kinship"
    assert AIJobStatus.QUEUED.value == "queued"
    assert AIJobStatus.RUNNING.value == "running"
    assert AIJobStatus.SUCCEEDED.value == "succeeded"
    assert AIJobStatus.FAILED.value == "failed"
    assert AIJobStatus.CANCELLED.value == "cancelled"


def test_ai_generation_job_model_uses_figure_data_schema() -> None:
    assert ai_jobs
    assert Base.metadata.tables["figure_data.ai_generation_jobs"].schema == "figure_data"


def test_ai_generation_job_model_declares_core_columns_and_constraints() -> None:
    table = Base.metadata.tables["figure_data.ai_generation_jobs"]

    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert table.c.id.primary_key
    assert not table.c.job_type.nullable
    assert not table.c.target_type.nullable
    assert not table.c.target_kind.nullable
    assert not table.c.target_id.nullable
    assert not table.c.status.nullable
    assert not table.c.created_by.nullable
    assert table.c.params.default is not None
    assert {
        "ck_ai_generation_jobs_job_type",
        "ck_ai_generation_jobs_target_type",
        "ck_ai_generation_jobs_target_kind",
        "ck_ai_generation_jobs_status",
    }.issubset(check_names)


def test_ai_generation_job_model_declares_worker_and_target_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_generation_jobs"]
    index_names = {index.name for index in table.indexes}

    assert {
        "ix_figure_data_ai_generation_jobs_status_created_at",
        "ix_figure_data_ai_generation_jobs_target",
        "ix_figure_data_ai_generation_jobs_job_type_created_at",
    }.issubset(index_names)


def test_ai_generation_jobs_has_queue_columns() -> None:
    table = Base.metadata.tables["figure_data.ai_generation_jobs"]

    for column_name in [
        "queue_backend",
        "queue_name",
        "queue_job_id",
        "enqueued_at",
        "attempt_count",
        "max_attempts",
        "next_run_at",
        "cancel_requested_at",
        "worker_id",
        "heartbeat_at",
    ]:
        assert column_name in table.c


def test_ai_generation_jobs_has_queue_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_generation_jobs"]
    index_names = {index.name for index in table.indexes}

    assert "ix_figure_data_ai_generation_jobs_queue_backend_status" in index_names
    assert "ix_figure_data_ai_generation_jobs_next_run_at" in index_names
