from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalSourceText:
    source_kind: str
    source_pk: str
    source_ref_id: int | None
    encounter_evidence_id: int | None
    source_work_id: int | None
    title_zh: str | None
    title_en: str | None
    pages: str | None
    text: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class RetrievalDocumentChunk:
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
    metadata: dict[str, object]


def normalize_retrieval_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def build_chunks(
    source: RetrievalSourceText,
    *,
    max_chars: int = 800,
) -> list[RetrievalDocumentChunk]:
    text = normalize_retrieval_text(source.text)
    if not text:
        return []
    parts = [text[index : index + max_chars] for index in range(0, len(text), max_chars)]
    return [
        RetrievalDocumentChunk(
            source_kind=source.source_kind,
            source_pk=source.source_pk,
            source_ref_id=source.source_ref_id,
            encounter_evidence_id=source.encounter_evidence_id,
            source_work_id=source.source_work_id,
            title_zh=source.title_zh,
            title_en=source.title_en,
            pages=source.pages,
            chunk_index=index,
            content_text=part,
            text_hash=_hash_text(part),
            metadata=source.metadata,
        )
        for index, part in enumerate(parts)
        if part
    ]


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
