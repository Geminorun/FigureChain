from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

from figure_data.sharing.types import ChainShareSnapshotRecord


@dataclass(frozen=True)
class MarkdownExportResult:
    content: str
    filename: str
    source_ids: dict[str, list[str]]


SOURCE_ID_KEYS = [
    "encounter_ids",
    "source_ref_ids",
    "source_work_ids",
    "ai_run_ids",
    "retrieval_document_ids",
]

WINDOWS_PATH_PATTERN = re.compile(r"\b[A-Za-z]:\\[^\s`'\"，。；;]+")
SECRET_PATTERNS = (
    re.compile(r"(postgresql|neo4j|bolt)://[^\s`'\"，。；;]+", re.IGNORECASE),
    re.compile(r"\b(?:OPENAI_API_KEY|DATABASE_URL|NEO4J_AUTH)\b[^\s`'\"，。；;]*"),
)


def render_chain_markdown(snapshot: ChainShareSnapshotRecord) -> MarkdownExportResult:
    people = _list_of_dicts(snapshot.path_payload.get("people"))
    edges = _list_of_dicts(snapshot.path_payload.get("edges"))
    source_ids = _empty_source_ids()
    for encounter_id in snapshot.encounter_ids:
        _append_unique(source_ids["encounter_ids"], encounter_id)

    lines = [
        "# FigureChain 人物链",
        "",
        f"{_endpoint_label(people, 0)} -> {_endpoint_label(people, -1)}",
        "",
        f"chain_hash: `{_sanitize(snapshot.chain_hash)}`",
        f"share_slug: `{_sanitize(snapshot.share_slug)}`",
        "",
        "## 路径人物",
        "",
    ]
    for index, person in enumerate(people, start=1):
        lines.append(f"{index}. {_person_label(person)}")
    lines.extend(["", "## 事实证据", ""])

    for index, edge in enumerate(edges, start=1):
        edge_encounter_id = _string(edge.get("encounter_id"))
        if edge_encounter_id:
            _append_unique(source_ids["encounter_ids"], edge_encounter_id)
        lines.append(f"### Edge {index}: `{_sanitize(edge_encounter_id or 'unknown')}`")
        lines.append(f"- kind: {_sanitize(_string(edge.get('encounter_kind')) or '未记录')}")
        lines.append(f"- certainty: {_sanitize(_string(edge.get('certainty_level')) or '未记录')}")
        lines.append(f"- pages: {_sanitize(_string(edge.get('pages')) or '未记录')}")
        summary = _string(edge.get("evidence_summary")) or "未记录"
        lines.append(f"- evidence: {_sanitize(summary)}")
        debug_note = _string(edge.get("debug_note"))
        if debug_note:
            lines.append(f"- note: {_sanitize(debug_note)}")
        direct_ref_id = _string(edge.get("source_ref_id"))
        direct_work_id = _string(edge.get("source_work_id"))
        if direct_ref_id or direct_work_id:
            _append_source_ref_line(
                lines,
                source_ids,
                ref_id=direct_ref_id,
                work_id=direct_work_id,
                title=None,
                pages=_string(edge.get("pages")),
            )
        for source_ref in _list_of_dicts(edge.get("source_refs")):
            ref_id = _string(source_ref.get("source_ref_id"))
            work_id = _string(source_ref.get("source_work_id"))
            _append_source_ref_line(
                lines,
                source_ids,
                ref_id=ref_id,
                work_id=work_id,
                title=_string(source_ref.get("title")),
                pages=_string(source_ref.get("pages")),
            )
        lines.append("")

    if snapshot.include_ai_explanation:
        _append_ai_section(lines, source_ids, snapshot.path_payload.get("ai_explanation"))

    if snapshot.include_rag_context:
        _append_rag_section(lines, source_ids, snapshot.path_payload.get("rag_context"))

    content = "\n".join(lines).strip() + "\n"
    return MarkdownExportResult(
        content=content,
        filename=f"figurechain-{_safe_filename_token(snapshot.chain_hash)}.md",
        source_ids=source_ids,
    )


def _append_ai_section(
    lines: list[str],
    source_ids: dict[str, list[str]],
    value: object,
) -> None:
    if not isinstance(value, dict):
        return
    ai_run_id = _string(value.get("ai_run_id"))
    if ai_run_id:
        _append_unique(source_ids["ai_run_ids"], ai_run_id)
    summary = _string(value.get("summary"))
    lines.extend(
        [
            "## AI 解释（非事实源）",
            "",
            f"- ai_run_id: {_sanitize(ai_run_id or '未记录')}",
            f"- summary: {_sanitize(summary or '未记录')}",
            "",
        ]
    )


def _append_rag_section(
    lines: list[str],
    source_ids: dict[str, list[str]],
    value: object,
) -> None:
    contexts = _list_of_dicts(value)
    if not contexts:
        return
    lines.extend(["## RAG 召回上下文（非事实源）", ""])
    for index, context in enumerate(contexts, start=1):
        document_id = _string(context.get("retrieval_document_id"))
        source_ref_id = _string(context.get("source_ref_id"))
        if document_id:
            _append_unique(source_ids["retrieval_document_ids"], document_id)
        if source_ref_id:
            _append_unique(source_ids["source_ref_ids"], source_ref_id)
        snippet = _string(context.get("snippet")) or "未记录"
        lines.append(
            f"{index}. document {document_id or '未记录'} / source_ref {source_ref_id or '未记录'}"
        )
        lines.append(f"   - {_sanitize(snippet)}")
    lines.append("")


def _endpoint_label(people: list[dict[str, object]], index: int) -> str:
    if not people:
        return "未记录"
    try:
        return _sanitize(_string(people[index].get("display_name")) or "未记录")
    except IndexError:
        return "未记录"


def _person_label(person: dict[str, object]) -> str:
    name = _string(person.get("display_name")) or "未记录"
    person_id = _string(person.get("person_id")) or "未记录"
    birth_year = _string(person.get("birth_year")) or "?"
    death_year = _string(person.get("death_year")) or "?"
    return f"{_sanitize(name)} (`{_sanitize(person_id)}`, {birth_year}-{death_year})"


def _empty_source_ids() -> dict[str, list[str]]:
    return {key: [] for key in SOURCE_ID_KEYS}


def _append_source_ref_line(
    lines: list[str],
    source_ids: dict[str, list[str]],
    *,
    ref_id: str | None,
    work_id: str | None,
    title: str | None,
    pages: str | None,
) -> None:
    if ref_id:
        _append_unique(source_ids["source_ref_ids"], ref_id)
    if work_id:
        _append_unique(source_ids["source_work_ids"], work_id)
    lines.append(
        f"- source_ref {ref_id or '未记录'} / source_work {work_id or '未记录'}"
        f" / pages {pages or '未记录'} / {_sanitize(title or '未记录题名')}"
    )


def _append_unique(values: list[str], value: object) -> None:
    text = str(value)
    if text and text not in values:
        values.append(text)


def _sanitize(value: str) -> str:
    result = WINDOWS_PATH_PATTERN.sub("[redacted-path]", value)
    for pattern in SECRET_PATTERNS:
        result = pattern.sub("[redacted-secret]", result)
    return result


def _safe_filename_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return token or "chain"


def _string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _list_of_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [cast(dict[str, object], item) for item in value if isinstance(item, dict)]
