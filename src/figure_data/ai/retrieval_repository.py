from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from figure_data.ai.retrieval_chunking import RetrievalDocumentChunk, RetrievalSourceText


@dataclass(frozen=True)
class RetrievalDocumentFilters:
    source_ref_id: int | None = None
    include_encounter_evidence: bool = True
    limit: int = 50


@dataclass(frozen=True)
class RetrievalSearchFilters:
    query_embedding: list[float]
    provider: str
    model_name: str
    limit: int = 5
    source_ref_id: int | None = None


@dataclass(frozen=True)
class RetrievalSearchResult:
    document_id: UUID
    source_kind: str
    source_pk: str
    source_ref_id: int | None
    encounter_evidence_id: int | None
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    chunk_index: int
    content_text: str
    text_hash: str
    score: float


def create_or_update_retrieval_document(
    session: Session,
    chunk: RetrievalDocumentChunk,
) -> UUID:
    value = session.execute(
        text(
            """
            insert into figure_data.ai_retrieval_documents (
              id, source_kind, source_pk, source_ref_id, encounter_evidence_id,
              source_work_id, title_zh, title_en, pages, chunk_index, content_text,
              text_hash, metadata_json, status, created_at, updated_at
            ) values (
              gen_random_uuid(), :source_kind, :source_pk, :source_ref_id,
              :encounter_evidence_id, :source_work_id, :title_zh, :title_en,
              :pages, :chunk_index, :content_text, :text_hash,
              cast(:metadata_json as jsonb), :status, :now, :now
            )
            on conflict on constraint uq_ai_retrieval_documents_source_chunk_hash
            do update set
              content_text = excluded.content_text,
              metadata_json = excluded.metadata_json,
              status = excluded.status,
              updated_at = excluded.updated_at
            returning id
            """
        ),
        {
            "source_kind": chunk.source_kind,
            "source_pk": chunk.source_pk,
            "source_ref_id": chunk.source_ref_id,
            "encounter_evidence_id": chunk.encounter_evidence_id,
            "source_work_id": chunk.source_work_id,
            "title_zh": chunk.title_zh,
            "title_en": chunk.title_en,
            "pages": chunk.pages,
            "chunk_index": chunk.chunk_index,
            "content_text": chunk.content_text,
            "text_hash": chunk.text_hash,
            "metadata_json": json.dumps(chunk.metadata, ensure_ascii=False),
            "status": "active",
            "now": datetime.now(UTC),
        },
    ).scalar_one()
    return value if isinstance(value, UUID) else UUID(str(value))


def upsert_retrieval_embedding(
    session: Session,
    *,
    document_id: UUID,
    provider: str,
    model_name: str,
    embedding: list[float],
    text_hash: str,
) -> None:
    session.execute(
        text(
            """
            insert into figure_data.ai_retrieval_embeddings (
              id, document_id, provider, model_name, embedding_dimensions,
              embedding, text_hash, created_at
            ) values (
              gen_random_uuid(), :document_id, :provider, :model_name,
              :embedding_dimensions, cast(:embedding as vector), :text_hash, :created_at
            )
            on conflict on constraint uq_ai_retrieval_embeddings_document_provider_model
            do update set
              embedding_dimensions = excluded.embedding_dimensions,
              embedding = excluded.embedding,
              text_hash = excluded.text_hash,
              created_at = excluded.created_at
            """
        ),
        {
            "document_id": document_id,
            "provider": provider,
            "model_name": model_name,
            "embedding_dimensions": len(embedding),
            "embedding": _vector_literal(embedding),
            "text_hash": text_hash,
            "created_at": datetime.now(UTC),
        },
    )


def list_retrieval_source_texts(
    session: Session,
    filters: RetrievalDocumentFilters,
) -> list[RetrievalSourceText]:
    rows = session.execute(_source_ref_query(filters), _source_ref_params(filters)).mappings().all()
    sources = [_source_text_from_row(cast(Mapping[str, Any], row)) for row in rows]
    if filters.include_encounter_evidence:
        evidence_rows = (
            session.execute(_encounter_evidence_query(filters), _source_ref_params(filters))
            .mappings()
            .all()
        )
        sources.extend(_source_text_from_row(cast(Mapping[str, Any], row)) for row in evidence_rows)
    return sources


def search_retrieval_embeddings(
    session: Session,
    filters: RetrievalSearchFilters,
) -> list[RetrievalSearchResult]:
    conditions = [
        "e.provider = :provider",
        "e.model_name = :model_name",
        "d.status = 'active'",
    ]
    params: dict[str, object] = {
        "provider": filters.provider,
        "model_name": filters.model_name,
        "query_embedding": _vector_literal(filters.query_embedding),
        "limit": filters.limit,
    }
    if filters.source_ref_id is not None:
        conditions.append("d.source_ref_id = :source_ref_id")
        params["source_ref_id"] = filters.source_ref_id
    where_clause = " and ".join(conditions)
    rows = (
        session.execute(
            text(
                f"""
                select
                  d.id as document_id,
                  d.source_kind,
                  d.source_pk,
                  d.source_ref_id,
                  d.encounter_evidence_id,
                  d.source_work_id,
                  d.title_zh,
                  d.title_en,
                  d.pages,
                  d.chunk_index,
                  d.content_text,
                  d.text_hash,
                  e.embedding <=> cast(:query_embedding as vector) as distance
                from figure_data.ai_retrieval_embeddings e
                join figure_data.ai_retrieval_documents d on d.id = e.document_id
                where {where_clause}
                order by e.embedding <=> cast(:query_embedding as vector)
                limit :limit
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [_search_result_from_row(cast(Mapping[str, Any], row)) for row in rows]


def _source_ref_query(filters: RetrievalDocumentFilters) -> TextClause:
    where_clause = "" if filters.source_ref_id is None else "where sr.id = :source_ref_id"
    return text(
        f"""
        select
          'source_ref' as source_kind,
          'source_ref:' || sr.id::text as source_pk,
          sr.id as source_ref_id,
          null::integer as encounter_evidence_id,
          sr.source_work_id,
          sw.title_zh,
          sw.title_en,
          sr.pages,
          concat_ws(' ', sw.title_zh, sw.title_en, sr.pages, sr.notes) as text,
          jsonb_build_object(
            'source_name', sr.source_name,
            'source_table', sr.source_table,
            'source_pk', sr.source_pk
          ) as metadata_json
        from figure_data.source_refs sr
        left join figure_data.source_works sw on sw.id = sr.source_work_id
        {where_clause}
        order by sr.id
        limit :limit
        """
    )


def _encounter_evidence_query(filters: RetrievalDocumentFilters) -> TextClause:
    where_clause = (
        ""
        if filters.source_ref_id is None
        else "where ev.source_ref_id = :source_ref_id"
    )
    return text(
        f"""
        select
          'encounter_evidence' as source_kind,
          'encounter_evidence:' || ev.id::text as source_pk,
          ev.source_ref_id,
          ev.id as encounter_evidence_id,
          ev.source_work_id,
          sw.title_zh,
          sw.title_en,
          ev.pages,
          concat_ws(' ', sw.title_zh, sw.title_en, ev.pages, ev.evidence_summary) as text,
          jsonb_build_object(
            'candidate_table', ev.candidate_table,
            'candidate_id', ev.candidate_id,
            'evidence_kind', ev.evidence_kind
          ) as metadata_json
        from figure_data.encounter_evidence ev
        left join figure_data.source_works sw on sw.id = ev.source_work_id
        {where_clause}
        order by ev.id
        limit :limit
        """
    )


def _source_ref_params(filters: RetrievalDocumentFilters) -> dict[str, object]:
    params: dict[str, object] = {"limit": filters.limit}
    if filters.source_ref_id is not None:
        params["source_ref_id"] = filters.source_ref_id
    return params


def _source_text_from_row(row: Mapping[str, Any]) -> RetrievalSourceText:
    return RetrievalSourceText(
        source_kind=str(row["source_kind"]),
        source_pk=str(row["source_pk"]),
        source_ref_id=_optional_int(row["source_ref_id"]),
        encounter_evidence_id=_optional_int(row["encounter_evidence_id"]),
        source_work_id=_optional_int(row["source_work_id"]),
        title_zh=_optional_str(row["title_zh"]),
        title_en=_optional_str(row["title_en"]),
        pages=_optional_str(row["pages"]),
        text=str(row["text"] or ""),
        metadata=dict(row["metadata_json"] or {}),
    )


def _search_result_from_row(row: Mapping[str, Any]) -> RetrievalSearchResult:
    distance = float(row["distance"])
    return RetrievalSearchResult(
        document_id=_uuid(row["document_id"]),
        source_kind=str(row["source_kind"]),
        source_pk=str(row["source_pk"]),
        source_ref_id=_optional_int(row["source_ref_id"]),
        encounter_evidence_id=_optional_int(row["encounter_evidence_id"]),
        source_work_id=_optional_int(row["source_work_id"]),
        title_zh=_optional_str(row["title_zh"]),
        title_en=_optional_str(row["title_en"]),
        pages=_optional_str(row["pages"]),
        chunk_index=int(row["chunk_index"]),
        content_text=str(row["content_text"]),
        text_hash=str(row["text_hash"]),
        score=round(1.0 - distance, 6),
    )


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(round(value, 8)) for value in values) + "]"


def _optional_int(value: object) -> int | None:
    return None if value is None else int(cast(Any, value))


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
