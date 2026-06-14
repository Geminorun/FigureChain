from dataclasses import dataclass
from typing import Any
from uuid import UUID

from figure_data.ai.retrieval_chunking import RetrievalDocumentChunk
from figure_data.ai.retrieval_repository import (
    RetrievalDocumentFilters,
    RetrievalSearchFilters,
    create_or_update_retrieval_document,
    list_retrieval_source_texts,
    mark_retrieval_documents_stale_for_sources,
    search_retrieval_embeddings,
    upsert_retrieval_embedding,
)


@dataclass
class ScalarResult:
    value: object

    def scalar_one(self) -> object:
        return self.value


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]
    rowcount: int = 0

    def mappings(self) -> "MappingResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []
        self.document_id = UUID("00000000-0000-0000-0000-000000000501")

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> object:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params or {})
        if "insert into figure_data.ai_retrieval_documents" in sql:
            return ScalarResult(self.document_id)
        if "update figure_data.ai_retrieval_documents" in sql:
            return MappingResult([], rowcount=1)
        if "from figure_data.source_refs" in sql:
            return MappingResult(
                [
                    {
                        "source_kind": "source_ref",
                        "source_pk": "source_ref:3853784",
                        "source_ref_id": 3853784,
                        "encounter_evidence_id": None,
                        "source_work_id": 111,
                        "title_zh": "续资治通鉴长编",
                        "title_en": None,
                        "pages": "卷一",
                        "text": "续资治通鉴长编 卷一 许几谒见韩琦。",
                        "metadata_json": {"source_table": "ASSOC_DATA"},
                    }
                ]
            )
        if "order by e.embedding <=> cast(:query_embedding as vector)" in sql:
            return MappingResult(
                [
                    {
                        "document_id": self.document_id,
                        "source_kind": "source_ref",
                        "source_pk": "source_ref:3853784",
                        "source_ref_id": 3853784,
                        "encounter_evidence_id": None,
                        "source_work_id": 111,
                        "title_zh": "续资治通鉴长编",
                        "title_en": None,
                        "pages": "卷一",
                        "chunk_index": 0,
                        "content_text": "许几谒见韩琦。",
                        "text_hash": "abc",
                        "distance": 0.12,
                    }
                ]
            )
        return MappingResult([])


def chunk() -> RetrievalDocumentChunk:
    return RetrievalDocumentChunk(
        source_kind="source_ref",
        source_pk="source_ref:3853784",
        source_ref_id=3853784,
        encounter_evidence_id=None,
        source_work_id=111,
        title_zh="续资治通鉴长编",
        title_en=None,
        pages="卷一",
        chunk_index=0,
        content_text="许几谒见韩琦。",
        text_hash="abc",
        metadata={"source_table": "ASSOC_DATA"},
    )


def test_create_or_update_retrieval_document_upserts_document() -> None:
    session = FakeSession()

    document_id = create_or_update_retrieval_document(
        session,  # type: ignore[arg-type]
        chunk(),
    )

    assert document_id == session.document_id
    assert "insert into figure_data.ai_retrieval_documents" in session.statements[0]
    assert (
        "on conflict on constraint uq_ai_retrieval_documents_source_chunk_hash"
        in session.statements[0]
    )
    assert session.params[0]["source_ref_id"] == 3853784
    assert session.params[0]["status"] == "active"


def test_upsert_retrieval_embedding_uses_vector_literal() -> None:
    session = FakeSession()

    upsert_retrieval_embedding(
        session,  # type: ignore[arg-type]
        document_id=session.document_id,
        provider="fake",
        model_name="fake-hash-embedding",
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        text_hash="abc",
    )

    assert "insert into figure_data.ai_retrieval_embeddings" in session.statements[0]
    assert session.params[0]["embedding"] == "[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8]"


def test_mark_retrieval_documents_stale_for_sources_uses_source_identity() -> None:
    session = FakeSession()

    count = mark_retrieval_documents_stale_for_sources(
        session,  # type: ignore[arg-type]
        [chunk()],
    )

    assert count == 1
    assert "update figure_data.ai_retrieval_documents" in session.statements[0]
    assert "source_kind = :source_kind" in session.statements[0]
    assert "source_pk = :source_pk" in session.statements[0]
    assert session.params[0]["source_kind"] == "source_ref"
    assert session.params[0]["source_pk"] == "source_ref:3853784"


def test_list_retrieval_source_texts_reads_source_refs() -> None:
    session = FakeSession()

    rows = list_retrieval_source_texts(
        session,  # type: ignore[arg-type]
        RetrievalDocumentFilters(source_ref_id=3853784, include_encounter_evidence=False, limit=5),
    )

    assert rows[0].source_ref_id == 3853784
    assert rows[0].text == "续资治通鉴长编 卷一 许几谒见韩琦。"


def test_search_retrieval_embeddings_orders_by_cosine_distance() -> None:
    session = FakeSession()

    rows = search_retrieval_embeddings(
        session,  # type: ignore[arg-type]
        RetrievalSearchFilters(
            query_embedding=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
            provider="fake",
            model_name="fake-hash-embedding",
            limit=5,
        ),
    )

    assert rows[0].source_ref_id == 3853784
    assert rows[0].score == 0.88
    assert "order by e.embedding <=> cast(:query_embedding as vector)" in session.statements[0]
