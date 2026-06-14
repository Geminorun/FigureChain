from uuid import UUID

from figure_data.ai.retrieval_formatting import (
    format_build_rag_index_result,
    format_search_rag_evidence_result,
)
from figure_data.ai.retrieval_repository import RetrievalSearchResult
from figure_data.ai.retrieval_service import BuildRagIndexResult, SearchRagEvidenceResult


def test_format_build_rag_index_result_outputs_counts() -> None:
    lines = format_build_rag_index_result(
        BuildRagIndexResult(
            sources_read=2,
            documents_indexed=2,
            embeddings_written=2,
            provider="fake",
            model_name="fake-hash-embedding",
        )
    )

    assert "rag_index\tsources_read\t2" in lines
    assert "rag_index\tembeddings_written\t2" in lines
    assert "embedding_model\tfake\tfake-hash-embedding" in lines


def test_format_search_rag_evidence_result_outputs_trace_rows() -> None:
    result = SearchRagEvidenceResult(
        query="许几 韩琦",
        provider="fake",
        model_name="fake-hash-embedding",
        results=[
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
        ],
    )

    lines = format_search_rag_evidence_result(result)

    assert "rag_query\t许几 韩琦" in lines
    assert "embedding_model\tfake\tfake-hash-embedding" in lines
    assert (
        "result\t0\t0.88\t00000000-0000-0000-0000-000000000501\t"
        "source_ref\tsource_ref:3853784\t3853784\t\t许几谒见韩琦。"
    ) in lines


def test_format_search_rag_evidence_result_outputs_document_and_evidence_ids() -> None:
    result = SearchRagEvidenceResult(
        query="许几 韩琦",
        provider="fake",
        model_name="fake-hash-embedding",
        results=[
            RetrievalSearchResult(
                document_id=UUID("00000000-0000-0000-0000-000000000502"),
                source_kind="encounter_evidence",
                source_pk="encounter_evidence:12",
                source_ref_id=3853784,
                encounter_evidence_id=12,
                source_work_id=111,
                title_zh=None,
                title_en=None,
                pages="卷一",
                chunk_index=0,
                content_text="许几谒见韩琦。",
                text_hash="def",
                score=0.77,
            )
        ],
    )

    lines = format_search_rag_evidence_result(result)

    assert (
        "result\t0\t0.77\t00000000-0000-0000-0000-000000000502\t"
        "encounter_evidence\tencounter_evidence:12\t3853784\t12\t许几谒见韩琦。"
    ) in lines
