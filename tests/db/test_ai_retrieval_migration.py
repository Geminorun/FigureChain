from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260613_0004_create_ai_retrieval_tables.py")


def test_ai_retrieval_migration_depends_on_chain_explanations() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "20260613_0004"' in migration_source
    assert 'down_revision: str | None = "20260613_0003"' in migration_source


def test_ai_retrieval_migration_creates_pgvector_extension_and_tables() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "create extension if not exists vector" in migration_source.lower()
    assert 'op.create_table("ai_retrieval_documents"' in migration_source
    assert "create table figure_data.ai_retrieval_embeddings" in migration_source
    assert "embedding vector(8) not null" in migration_source


def test_ai_retrieval_migration_declares_rebuildable_indexes() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "uq_ai_retrieval_documents_source_chunk_hash" in migration_source
    assert "uq_ai_retrieval_embeddings_document_provider_model" in migration_source
    assert "using hnsw (embedding vector_cosine_ops)" in migration_source.lower()
