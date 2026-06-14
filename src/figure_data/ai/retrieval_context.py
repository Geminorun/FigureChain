from __future__ import annotations

import re

from pydantic import BaseModel, Field

from figure_data.ai.retrieval_repository import RetrievalSearchResult


class AIRetrievalContextItem(BaseModel):
    document_id: str
    source_kind: str
    source_pk: str
    source_ref_id: int | None
    encounter_evidence_id: int | None
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    score: float
    snippet: str = Field(min_length=1, max_length=500)
    provider: str
    model_name: str
    embedding_dimensions: int


def retrieval_context_items_from_search_results(
    results: list[RetrievalSearchResult],
    *,
    provider: str,
    model_name: str,
    embedding_dimensions: int,
    snippet_chars: int = 240,
) -> list[AIRetrievalContextItem]:
    items: list[AIRetrievalContextItem] = []
    for result in results:
        snippet = _snippet(result.content_text, snippet_chars=snippet_chars)
        if not snippet:
            continue
        items.append(
            AIRetrievalContextItem(
                document_id=str(result.document_id),
                source_kind=result.source_kind,
                source_pk=result.source_pk,
                source_ref_id=result.source_ref_id,
                encounter_evidence_id=result.encounter_evidence_id,
                source_work_id=result.source_work_id,
                title_zh=result.title_zh,
                title_en=result.title_en,
                pages=result.pages,
                score=result.score,
                snippet=snippet,
                provider=provider,
                model_name=model_name,
                embedding_dimensions=embedding_dimensions,
            )
        )
    return items


def retrieval_document_ids(items: list[AIRetrievalContextItem]) -> set[str]:
    return {item.document_id for item in items}


def retrieval_source_ref_ids(items: list[AIRetrievalContextItem]) -> set[int]:
    return {item.source_ref_id for item in items if item.source_ref_id is not None}


def build_candidate_retrieval_query(
    *,
    person_a_names: list[str | None],
    person_b_names: list[str | None],
    relation_label: str | None,
    candidate_basis: str | None,
    source_titles: list[str | None],
    notes: list[str | None],
) -> str:
    return _join_terms(
        [
            *person_a_names,
            *person_b_names,
            relation_label,
            candidate_basis,
            *source_titles,
            *notes,
        ]
    )


def build_chain_retrieval_queries(
    *,
    people_names: list[str],
    encounter_summaries: list[str],
    source_ref_ids: list[int],
) -> list[tuple[int, str]]:
    query = _join_terms([*people_names, *encounter_summaries])
    seen: set[int] = set()
    scoped_queries: list[tuple[int, str]] = []
    for source_ref_id in source_ref_ids:
        if source_ref_id in seen:
            continue
        seen.add(source_ref_id)
        scoped_queries.append((source_ref_id, query))
    return scoped_queries


def _join_terms(values: list[str | None]) -> str:
    return " ".join(value.strip() for value in values if value and value.strip())


def _snippet(value: str, *, snippet_chars: int) -> str:
    return re.sub(r"\s+", " ", value).strip()[:snippet_chars]
