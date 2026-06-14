from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.ai.embedding_provider import EmbeddingProvider, create_embedding_provider
from figure_data.ai.retrieval_chunking import (
    RetrievalDocumentChunk,
    RetrievalSourceText,
    build_chunks,
)
from figure_data.ai.retrieval_repository import (
    RetrievalDocumentFilters,
    RetrievalSearchFilters,
    RetrievalSearchResult,
    create_or_update_retrieval_document,
    list_retrieval_source_texts,
    search_retrieval_embeddings,
    upsert_retrieval_embedding,
)


class RetrievalSettings(Protocol):
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int


class RetrievalRepository(Protocol):
    def list_sources(
        self,
        session: object,
        filters: RetrievalDocumentFilters,
    ) -> list[RetrievalSourceText]:
        """List source texts to index."""

    def create_document(self, session: object, chunk: RetrievalDocumentChunk) -> UUID:
        """Create or update one retrieval document."""

    def upsert_embedding(self, session: object, **kwargs: object) -> None:
        """Upsert one retrieval embedding."""

    def search(
        self,
        session: object,
        filters: RetrievalSearchFilters,
    ) -> list[RetrievalSearchResult]:
        """Search retrieval embeddings."""


class PostgresRetrievalRepository:
    def list_sources(
        self,
        session: object,
        filters: RetrievalDocumentFilters,
    ) -> list[RetrievalSourceText]:
        return list_retrieval_source_texts(session, filters)  # type: ignore[arg-type]

    def create_document(self, session: object, chunk: RetrievalDocumentChunk) -> UUID:
        return create_or_update_retrieval_document(session, chunk)  # type: ignore[arg-type]

    def upsert_embedding(self, session: object, **kwargs: object) -> None:
        upsert_retrieval_embedding(session, **kwargs)  # type: ignore[arg-type]

    def search(
        self,
        session: object,
        filters: RetrievalSearchFilters,
    ) -> list[RetrievalSearchResult]:
        return search_retrieval_embeddings(session, filters)  # type: ignore[arg-type]


@dataclass(frozen=True)
class BuildRagIndexOptions:
    source_ref_id: int | None
    limit: int
    include_encounter_evidence: bool


@dataclass(frozen=True)
class BuildRagIndexResult:
    sources_read: int
    documents_indexed: int
    embeddings_written: int
    provider: str
    model_name: str


@dataclass(frozen=True)
class SearchRagEvidenceOptions:
    query: str
    source_ref_id: int | None
    limit: int


@dataclass(frozen=True)
class SearchRagEvidenceResult:
    query: str
    provider: str
    model_name: str
    results: list[RetrievalSearchResult]


def build_rag_index(
    *,
    session: Session | object,
    settings: RetrievalSettings,
    options: BuildRagIndexOptions,
    provider: EmbeddingProvider | None = None,
    repository: RetrievalRepository | None = None,
) -> BuildRagIndexResult:
    resolved_provider = provider or create_embedding_provider(settings)
    resolved_repository = repository or PostgresRetrievalRepository()
    model_name = settings.embedding_model
    sources = resolved_repository.list_sources(
        session,
        RetrievalDocumentFilters(
            source_ref_id=options.source_ref_id,
            include_encounter_evidence=options.include_encounter_evidence,
            limit=options.limit,
        ),
    )
    chunks = [chunk for source in sources for chunk in build_chunks(source)]
    if not chunks:
        return BuildRagIndexResult(
            sources_read=len(sources),
            documents_indexed=0,
            embeddings_written=0,
            provider=resolved_provider.provider_name,
            model_name=model_name,
        )
    response = resolved_provider.embed(
        [chunk.content_text for chunk in chunks],
        model_name=model_name,
    )
    embeddings_written = 0
    for chunk, embedding in zip(chunks, response.vectors, strict=True):
        document_id = resolved_repository.create_document(session, chunk)
        resolved_repository.upsert_embedding(
            session,
            document_id=document_id,
            provider=response.provider,
            model_name=response.model_name,
            embedding=embedding,
            text_hash=chunk.text_hash,
        )
        embeddings_written += 1
    return BuildRagIndexResult(
        sources_read=len(sources),
        documents_indexed=len(chunks),
        embeddings_written=embeddings_written,
        provider=response.provider,
        model_name=response.model_name,
    )


def search_rag_evidence(
    *,
    session: Session | object,
    settings: RetrievalSettings,
    options: SearchRagEvidenceOptions,
    provider: EmbeddingProvider | None = None,
    repository: RetrievalRepository | None = None,
) -> SearchRagEvidenceResult:
    query = options.query.strip()
    if not query:
        raise ValueError("query is required")
    resolved_provider = provider or create_embedding_provider(settings)
    resolved_repository = repository or PostgresRetrievalRepository()
    response = resolved_provider.embed([query], model_name=settings.embedding_model)
    results = resolved_repository.search(
        session,
        RetrievalSearchFilters(
            query_embedding=response.vectors[0],
            provider=response.provider,
            model_name=response.model_name,
            limit=options.limit,
            source_ref_id=options.source_ref_id,
        ),
    )
    return SearchRagEvidenceResult(
        query=query,
        provider=response.provider,
        model_name=response.model_name,
        results=results,
    )
