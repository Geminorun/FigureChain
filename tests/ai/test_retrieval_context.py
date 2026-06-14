from uuid import UUID

from figure_data.ai.retrieval_context import (
    AIRetrievalContextItem,
    build_candidate_retrieval_query,
    build_chain_retrieval_queries,
    retrieval_context_items_from_search_results,
    retrieval_document_ids,
    retrieval_source_ref_ids,
)
from figure_data.ai.retrieval_repository import RetrievalSearchResult


def search_result(
    *,
    document_id: str = "00000000-0000-0000-0000-000000000501",
    source_kind: str = "source_ref",
    source_pk: str = "source_ref:3853784",
    source_ref_id: int | None = 3853784,
    encounter_evidence_id: int | None = None,
    content_text: str = "Xu Ji met Han Qi. Page one.",
) -> RetrievalSearchResult:
    return RetrievalSearchResult(
        document_id=UUID(document_id),
        source_kind=source_kind,
        source_pk=source_pk,
        source_ref_id=source_ref_id,
        encounter_evidence_id=encounter_evidence_id,
        source_work_id=111,
        title_zh="Xu zizhi tongjian changbian",
        title_en=None,
        pages="juan 1",
        chunk_index=0,
        content_text=content_text,
        text_hash="abc",
        score=0.88,
    )


def test_retrieval_context_items_preserve_trace_fields_and_snippet() -> None:
    items = retrieval_context_items_from_search_results(
        [search_result()],
        provider="fake",
        model_name="fake-hash-embedding",
        embedding_dimensions=8,
    )

    assert items == [
        AIRetrievalContextItem(
            document_id="00000000-0000-0000-0000-000000000501",
            source_kind="source_ref",
            source_pk="source_ref:3853784",
            source_ref_id=3853784,
            encounter_evidence_id=None,
            source_work_id=111,
            title_zh="Xu zizhi tongjian changbian",
            title_en=None,
            pages="juan 1",
            score=0.88,
            snippet="Xu Ji met Han Qi. Page one.",
            provider="fake",
            model_name="fake-hash-embedding",
            embedding_dimensions=8,
        )
    ]


def test_retrieval_context_limits_snippet_length() -> None:
    items = retrieval_context_items_from_search_results(
        [search_result(content_text="a" * 240)],
        provider="fake",
        model_name="fake-hash-embedding",
        embedding_dimensions=8,
        snippet_chars=20,
    )

    assert items[0].snippet == "a" * 20


def test_retrieval_context_id_helpers_ignore_missing_values() -> None:
    items = retrieval_context_items_from_search_results(
        [
            search_result(),
            search_result(
                document_id="00000000-0000-0000-0000-000000000502",
                source_kind="encounter_evidence",
                source_pk="encounter_evidence:12",
                source_ref_id=3853784,
                encounter_evidence_id=12,
            ),
            search_result(
                document_id="00000000-0000-0000-0000-000000000501",
                source_ref_id=None,
            ),
        ],
        provider="fake",
        model_name="fake-hash-embedding",
        embedding_dimensions=8,
    )

    assert retrieval_document_ids(items) == {
        "00000000-0000-0000-0000-000000000501",
        "00000000-0000-0000-0000-000000000502",
    }
    assert retrieval_source_ref_ids(items) == {3853784}


def test_build_candidate_retrieval_query_uses_candidate_people_and_sources() -> None:
    query = build_candidate_retrieval_query(
        person_a_names=["Xu Ji", None],
        person_b_names=["Han Qi"],
        relation_label="met",
        candidate_basis="direct_interaction_likely",
        source_titles=["Xu zizhi tongjian changbian"],
        notes=["Xu Ji met Han Qi at Wei."],
    )

    assert query == (
        "Xu Ji Han Qi met direct_interaction_likely "
        "Xu zizhi tongjian changbian Xu Ji met Han Qi at Wei."
    )


def test_build_chain_retrieval_queries_scope_by_source_ref() -> None:
    queries = build_chain_retrieval_queries(
        people_names=["Xu Ji", "Han Qi"],
        encounter_summaries=["Xu Ji met Han Qi at Wei."],
        source_ref_ids=[3853784, 3853784, 3853790],
    )

    assert queries == [
        (3853784, "Xu Ji Han Qi Xu Ji met Han Qi at Wei."),
        (3853790, "Xu Ji Han Qi Xu Ji met Han Qi at Wei."),
    ]
