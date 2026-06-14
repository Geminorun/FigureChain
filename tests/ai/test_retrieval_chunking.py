from figure_data.ai.retrieval_chunking import (
    RetrievalSourceText,
    build_chunks,
    normalize_retrieval_text,
)


def test_normalize_retrieval_text_collapses_whitespace() -> None:
    assert normalize_retrieval_text("  许几\n\n曾谒见 韩琦。") == "许几 曾谒见 韩琦。"


def test_build_chunks_keeps_short_text_as_one_chunk() -> None:
    source = RetrievalSourceText(
        source_kind="source_ref",
        source_pk="source_ref:3853784",
        source_ref_id=3853784,
        encounter_evidence_id=None,
        source_work_id=111,
        title_zh="续资治通鉴长编",
        title_en=None,
        pages="卷一",
        text="许几曾谒见韩琦。",
        metadata={"source": "test"},
    )

    chunks = build_chunks(source, max_chars=80)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].content_text == "许几曾谒见韩琦。"
    assert len(chunks[0].text_hash) == 64


def test_build_chunks_splits_long_text_without_empty_chunks() -> None:
    source = RetrievalSourceText(
        source_kind="encounter_evidence",
        source_pk="encounter_evidence:1",
        source_ref_id=3853784,
        encounter_evidence_id=1,
        source_work_id=111,
        title_zh=None,
        title_en=None,
        pages="卷一",
        text="甲" * 120,
        metadata={},
    )

    chunks = build_chunks(source, max_chars=50)

    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert all(chunk.content_text for chunk in chunks)
    assert all(chunk.source_kind == "encounter_evidence" for chunk in chunks)
