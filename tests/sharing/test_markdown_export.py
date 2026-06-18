from datetime import UTC, datetime
from uuid import UUID

from figure_data.sharing.markdown import render_chain_markdown
from figure_data.sharing.types import ChainShareSnapshotRecord


def snapshot(*, include_ai: bool = True, include_rag: bool = True) -> ChainShareSnapshotRecord:
    return ChainShareSnapshotRecord(
        id=UUID("00000000-0000-0000-0000-000000000501"),
        share_slug="20260619-test",
        source_person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
        target_person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
        chain_hash="known-chain-hash",
        encounter_ids=["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
        path_payload={
            "people": [
                {
                    "person_id": "38966b03-8aa7-5143-8021-2d266889b6c5",
                    "display_name": "許幾",
                    "birth_year": 1054,
                    "death_year": 1115,
                },
                {
                    "person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9",
                    "display_name": "韓琦",
                    "birth_year": 1008,
                    "death_year": 1075,
                },
            ],
            "edges": [
                {
                    "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                    "encounter_kind": "direct_interaction",
                    "certainty_level": "high",
                    "evidence_summary": "许几谒韩琦于魏",
                    "pages": "11905",
                    "source_refs": [
                        {
                            "source_ref_id": 3853784,
                            "source_work_id": 7596,
                            "title": "宋史",
                            "pages": "11905",
                        }
                    ],
                    "debug_note": "local file F:\\13.FigureChain\\FigureChain\\.env",
                }
            ],
            "ai_explanation": {
                "ai_run_id": "00000000-0000-0000-0000-000000000601",
                "summary": "AI 认为这是直接见面证据，DATABASE_URL=postgresql://secret",
            },
            "rag_context": [
                {
                    "retrieval_document_id": "00000000-0000-0000-0000-000000000701",
                    "source_ref_id": 3853784,
                    "snippet": "OPENAI_API_KEY should not leak; 原文片段",
                }
            ],
        },
        filters_applied={"max_depth": 12},
        include_ai_explanation=include_ai,
        include_rag_context=include_rag,
        schema_version="share-v1",
        created_by="lyl",
        created_at=datetime(2026, 6, 19, tzinfo=UTC),
    )


def test_markdown_includes_fact_evidence_and_trace_ids() -> None:
    result = render_chain_markdown(snapshot())

    assert result.filename == "figurechain-known-chain-hash.md"
    assert "# FigureChain 人物链" in result.content
    assert "許幾 -> 韓琦" in result.content
    assert "chain_hash: `known-chain-hash`" in result.content
    assert "## 事实证据" in result.content
    assert "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f" in result.content
    assert "许几谒韩琦于魏" in result.content
    assert "source_ref 3853784" in result.content
    assert "source_work 7596" in result.content


def test_markdown_only_includes_ai_and_rag_when_enabled() -> None:
    enabled = render_chain_markdown(snapshot(include_ai=True, include_rag=True))
    disabled = render_chain_markdown(snapshot(include_ai=False, include_rag=False))

    assert "## AI 解释（非事实源）" in enabled.content
    assert "AI 认为这是直接见面证据" in enabled.content
    assert "## RAG 召回上下文（非事实源）" in enabled.content
    assert "原文片段" in enabled.content
    assert "## AI 解释（非事实源）" not in disabled.content
    assert "## RAG 召回上下文（非事实源）" not in disabled.content


def test_markdown_sanitizes_sensitive_runtime_text() -> None:
    result = render_chain_markdown(snapshot())

    assert "F:\\13.FigureChain" not in result.content
    assert "postgresql://secret" not in result.content
    assert "OPENAI_API_KEY" not in result.content
    assert "[redacted-path]" in result.content
    assert "[redacted-secret]" in result.content


def test_markdown_returns_grouped_source_ids() -> None:
    result = render_chain_markdown(snapshot())

    assert result.source_ids == {
        "encounter_ids": ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
        "source_ref_ids": ["3853784"],
        "source_work_ids": ["7596"],
        "ai_run_ids": ["00000000-0000-0000-0000-000000000601"],
        "retrieval_document_ids": ["00000000-0000-0000-0000-000000000701"],
    }


def test_markdown_collects_direct_edge_source_ids() -> None:
    record = snapshot(include_ai=False, include_rag=False)
    edge = record.path_payload["edges"][0]  # type: ignore[index]
    edge.pop("source_refs")
    edge["source_ref_id"] = 3853784
    edge["source_work_id"] = 7596

    result = render_chain_markdown(record)

    assert "source_ref 3853784" in result.content
    assert "source_work 7596" in result.content
    assert result.source_ids["source_ref_ids"] == ["3853784"]
    assert result.source_ids["source_work_ids"] == ["7596"]
