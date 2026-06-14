from sqlalchemy import CheckConstraint, UniqueConstraint

from figure_data.db.base import Base
from figure_data.db.models import ai_retrieval
from figure_data.db.vector import PgVector


def test_ai_retrieval_models_use_figure_data_schema() -> None:
    assert ai_retrieval
    assert Base.metadata.tables["figure_data.ai_retrieval_documents"].schema == "figure_data"
    assert Base.metadata.tables["figure_data.ai_retrieval_embeddings"].schema == "figure_data"


def test_ai_retrieval_documents_declare_constraints_and_indexes() -> None:
    table = Base.metadata.tables["figure_data.ai_retrieval_documents"]
    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    index_names = {index.name for index in table.indexes}

    assert "ck_ai_retrieval_documents_source_kind" in check_names
    assert "ck_ai_retrieval_documents_status" in check_names
    assert ("source_kind", "source_pk", "chunk_index", "text_hash") in unique_columns
    assert {
        "ix_figure_data_ai_retrieval_documents_source_ref_id",
        "ix_figure_data_ai_retrieval_documents_encounter_evidence_id",
        "ix_figure_data_ai_retrieval_documents_status",
        "ix_figure_data_ai_retrieval_documents_text_hash",
    }.issubset(index_names)


def test_ai_retrieval_embeddings_declare_vector_column() -> None:
    table = Base.metadata.tables["figure_data.ai_retrieval_embeddings"]
    index_names = {index.name for index in table.indexes}
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert isinstance(table.c.embedding.type, PgVector)
    assert table.c.embedding.type.dimensions == 8
    assert ("document_id", "provider", "model_name") in unique_columns
    assert {
        "ix_figure_data_ai_retrieval_embeddings_document_id",
        "ix_figure_data_ai_retrieval_embeddings_model",
    }.issubset(index_names)
