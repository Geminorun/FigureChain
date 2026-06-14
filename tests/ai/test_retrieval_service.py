from dataclasses import dataclass, field
from types import SimpleNamespace
from uuid import UUID

from figure_data.ai.embedding_provider import EmbeddingBatchResponse
from figure_data.ai.retrieval_chunking import RetrievalSourceText
from figure_data.ai.retrieval_repository import RetrievalSearchResult
from figure_data.ai.retrieval_service import (
    BuildRagIndexOptions,
    BuildRagIndexResult,
    SearchRagEvidenceOptions,
    build_rag_index,
    search_rag_evidence,
)


class FakeEmbeddingProvider:
    provider_name = "fake"

    def embed(self, texts: list[str], *, model_name: str) -> EmbeddingBatchResponse:
        return EmbeddingBatchResponse(
            vectors=[[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8] for _ in texts],
            provider=self.provider_name,
            model_name=model_name,
            dimensions=8,
        )


@dataclass
class FakeRepository:
    source_texts: list[RetrievalSourceText]
    stale_sources: list[object] = field(default_factory=list)
    created_documents: list[object] = field(default_factory=list)
    created_embeddings: list[dict[str, object]] = field(default_factory=list)

    def list_sources(self, session: object, filters: object) -> list[RetrievalSourceText]:
        return self.source_texts

    def create_document(self, session: object, chunk: object) -> UUID:
        self.created_documents.append(chunk)
        return UUID("00000000-0000-0000-0000-000000000501")

    def mark_stale_for_sources(self, session: object, sources: object) -> int:
        self.stale_sources.append(sources)
        return 1

    def upsert_embedding(self, session: object, **kwargs: object) -> None:
        self.created_embeddings.append(kwargs)

    def search(self, session: object, filters: object) -> list[RetrievalSearchResult]:
        return [
            RetrievalSearchResult(
                document_id=UUID("00000000-0000-0000-0000-000000000501"),
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
                score=0.88,
            )
        ]


def source_text() -> RetrievalSourceText:
    return RetrievalSourceText(
        source_kind="source_ref",
        source_pk="source_ref:3853784",
        source_ref_id=3853784,
        encounter_evidence_id=None,
        source_work_id=111,
        title_zh="续资治通鉴长编",
        title_en=None,
        pages="卷一",
        text="许几谒见韩琦。",
        metadata={"source": "test"},
    )


def settings() -> SimpleNamespace:
    return SimpleNamespace(
        embedding_provider="fake",
        embedding_model="fake-hash-embedding",
        embedding_dimensions=8,
        embedding_batch_size=16,
    )


def test_build_rag_index_creates_documents_and_embeddings() -> None:
    repository = FakeRepository([source_text()])

    result = build_rag_index(
        session=object(),
        settings=settings(),
        options=BuildRagIndexOptions(
            source_ref_id=3853784,
            limit=5,
            include_encounter_evidence=True,
        ),
        provider=FakeEmbeddingProvider(),
        repository=repository,
    )

    assert isinstance(result, BuildRagIndexResult)
    assert result.sources_read == 1
    assert result.documents_indexed == 1
    assert result.embeddings_written == 1
    assert repository.stale_sources
    assert repository.created_embeddings[0]["provider"] == "fake"


def test_build_rag_index_stales_old_documents_even_when_source_has_no_chunks() -> None:
    repository = FakeRepository(
        [
            RetrievalSourceText(
                source_kind="source_ref",
                source_pk="source_ref:3853784",
                source_ref_id=3853784,
                encounter_evidence_id=None,
                source_work_id=111,
                title_zh=None,
                title_en=None,
                pages=None,
                text=" ",
                metadata={},
            )
        ]
    )

    result = build_rag_index(
        session=object(),
        settings=settings(),
        options=BuildRagIndexOptions(
            source_ref_id=3853784,
            limit=5,
            include_encounter_evidence=True,
        ),
        provider=FakeEmbeddingProvider(),
        repository=repository,
    )

    assert result.documents_indexed == 0
    assert result.embeddings_written == 0
    assert repository.stale_sources


def test_search_rag_evidence_embeds_query_and_searches_repository() -> None:
    repository = FakeRepository([source_text()])

    result = search_rag_evidence(
        session=object(),
        settings=settings(),
        options=SearchRagEvidenceOptions(query="许几 韩琦", source_ref_id=None, limit=5),
        provider=FakeEmbeddingProvider(),
        repository=repository,
    )

    assert result.query == "许几 韩琦"
    assert result.provider == "fake"
    assert result.results[0].source_ref_id == 3853784
    assert result.results[0].score == 0.88
