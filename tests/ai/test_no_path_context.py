from uuid import UUID

from pytest import MonkeyPatch, raises

from figure_data.ai.no_path_context import (
    InvalidNoPathContextError,
    NoPathCandidateSummaryInput,
    NoPathEndpointGraphStatsInput,
    NoPathPersonInput,
    NoPathRetrievalContextInput,
    assemble_no_path_prompt_input,
    build_no_path_prompt_input,
    build_no_path_retrieval_query,
    no_path_allowed_candidate_keys,
    no_path_allowed_person_ids,
    no_path_allowed_retrieval_document_ids,
    no_path_allowed_source_ref_ids,
    retrieval_context_from_search_results,
)
from figure_data.ai.retrieval_repository import RetrievalSearchResult
from figure_data.graph.types import ChainLookupResult, ChainPath

SOURCE_PERSON_ID = "38966b03-8aa7-5143-8021-2d266889b6c5"
TARGET_PERSON_ID = "46cfdf66-08c4-5876-964b-4a95d098afe9"


def no_path_result() -> ChainLookupResult:
    return ChainLookupResult(
        source_person_id=SOURCE_PERSON_ID,
        target_person_id=TARGET_PERSON_ID,
        max_depth=12,
        path=None,
    )


def person(person_id: str, name: str) -> NoPathPersonInput:
    return NoPathPersonInput(
        person_id=person_id,
        display_name=name,
        birth_year=1010,
        death_year=1080,
        cbdb_external_id="123",
    )


def test_assemble_no_path_prompt_input_requires_no_path() -> None:
    result = ChainLookupResult(
        source_person_id=SOURCE_PERSON_ID,
        target_person_id=TARGET_PERSON_ID,
        max_depth=12,
        path=ChainPath(people=(), edges=()),
    )

    with raises(InvalidNoPathContextError, match="requires a no-path result"):
        assemble_no_path_prompt_input(
            result=result,
            people={
                SOURCE_PERSON_ID: person(SOURCE_PERSON_ID, "Xu Ji"),
                TARGET_PERSON_ID: person(TARGET_PERSON_ID, "Han Qi"),
            },
            endpoint_stats={
                SOURCE_PERSON_ID: NoPathEndpointGraphStatsInput(
                    person_id=SOURCE_PERSON_ID,
                    active_path_encounter_count=1,
                ),
                TARGET_PERSON_ID: NoPathEndpointGraphStatsInput(
                    person_id=TARGET_PERSON_ID,
                    active_path_encounter_count=2,
                ),
            },
            candidate_summaries=[],
            retrieval_context=[],
            language="zh-Hans",
        )


def test_assemble_no_path_prompt_input_preserves_traceable_context() -> None:
    candidate = NoPathCandidateSummaryInput(
        candidate_kind="relationship",
        candidate_id=960698,
        person_a_id=SOURCE_PERSON_ID,
        person_b_id="00000000-0000-0000-0000-000000000999",
        person_a_name="Xu Ji",
        person_b_name="Nearby person",
        candidate_strength="high",
        candidate_basis="direct_interaction_likely",
        relation_label="met",
        source_work_id=111,
        source_ref_id=3853784,
        pages="juan 1",
        review_status="unreviewed",
    )
    retrieval = NoPathRetrievalContextInput(
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
        snippet="Xu Ji met Han Qi.",
    )

    prompt_input = assemble_no_path_prompt_input(
        result=no_path_result(),
        people={
            SOURCE_PERSON_ID: person(SOURCE_PERSON_ID, "Xu Ji"),
            TARGET_PERSON_ID: person(TARGET_PERSON_ID, "Han Qi"),
        },
        endpoint_stats={
            SOURCE_PERSON_ID: NoPathEndpointGraphStatsInput(
                person_id=SOURCE_PERSON_ID,
                active_path_encounter_count=1,
            ),
            TARGET_PERSON_ID: NoPathEndpointGraphStatsInput(
                person_id=TARGET_PERSON_ID,
                active_path_encounter_count=2,
            ),
        },
        candidate_summaries=[candidate],
        retrieval_context=[retrieval],
        language="zh-Hans",
    )

    assert prompt_input.path_status == "no_path"
    assert prompt_input.source_person.display_name == "Xu Ji"
    assert prompt_input.target_person.display_name == "Han Qi"
    assert prompt_input.candidate_summaries == [candidate]
    assert prompt_input.retrieval_context == [retrieval]
    assert no_path_allowed_candidate_keys(prompt_input) == {("relationship", 960698)}
    assert no_path_allowed_source_ref_ids(prompt_input) == {3853784}
    assert no_path_allowed_retrieval_document_ids(prompt_input) == {
        "00000000-0000-0000-0000-000000000501"
    }
    assert no_path_allowed_person_ids(prompt_input) == {SOURCE_PERSON_ID, TARGET_PERSON_ID}


def test_retrieval_context_from_search_results_normalizes_snippet() -> None:
    result = RetrievalSearchResult(
        document_id=UUID("00000000-0000-0000-0000-000000000501"),
        source_kind="source_ref",
        source_pk="source_ref:3853784",
        source_ref_id=3853784,
        encounter_evidence_id=None,
        source_work_id=111,
        title_zh="Xu zizhi tongjian changbian",
        title_en=None,
        pages="juan 1",
        chunk_index=0,
        content_text="Xu Ji\n\tmet Han Qi.",
        text_hash="abc",
        score=0.88,
    )

    items = retrieval_context_from_search_results([result], snippet_chars=20)

    assert items[0].document_id == "00000000-0000-0000-0000-000000000501"
    assert items[0].snippet == "Xu Ji met Han Qi."


def test_build_no_path_retrieval_query_uses_endpoint_and_candidate_names() -> None:
    prompt_input = assemble_no_path_prompt_input(
        result=no_path_result(),
        people={
            SOURCE_PERSON_ID: person(SOURCE_PERSON_ID, "Xu Ji"),
            TARGET_PERSON_ID: person(TARGET_PERSON_ID, "Han Qi"),
        },
        endpoint_stats={
            SOURCE_PERSON_ID: NoPathEndpointGraphStatsInput(
                person_id=SOURCE_PERSON_ID,
                active_path_encounter_count=1,
            ),
            TARGET_PERSON_ID: NoPathEndpointGraphStatsInput(
                person_id=TARGET_PERSON_ID,
                active_path_encounter_count=2,
            ),
        },
        candidate_summaries=[
            NoPathCandidateSummaryInput(
                candidate_kind="relationship",
                candidate_id=960698,
                person_a_id=SOURCE_PERSON_ID,
                person_b_id="00000000-0000-0000-0000-000000000999",
                person_a_name="Xu Ji",
                person_b_name="Nearby person",
                candidate_strength="high",
                candidate_basis="direct_interaction_likely",
                relation_label="met",
                source_work_id=111,
                source_ref_id=3853784,
                pages="juan 1",
                review_status="unreviewed",
            )
        ],
        retrieval_context=[],
        language="zh-Hans",
    )

    assert build_no_path_retrieval_query(prompt_input) == (
        "Xu Ji Han Qi Xu Ji Nearby person met"
    )


def test_build_no_path_prompt_input_uses_repository_helpers(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "figure_data.ai.no_path_context._load_people_by_ids",
        lambda session, person_ids: {
            SOURCE_PERSON_ID: person(SOURCE_PERSON_ID, "Xu Ji"),
            TARGET_PERSON_ID: person(TARGET_PERSON_ID, "Han Qi"),
        },
    )
    monkeypatch.setattr(
        "figure_data.ai.no_path_context._count_active_path_encounters",
        lambda session, person_id: 3,
    )
    monkeypatch.setattr(
        "figure_data.ai.no_path_context._list_endpoint_candidate_summaries",
        lambda session, person_ids, limit: [],
    )

    prompt_input = build_no_path_prompt_input(
        session=object(),
        result=no_path_result(),
        retrieval_context=[],
        candidate_limit=5,
        language="zh-Hans",
    )

    assert prompt_input.source_stats.active_path_encounter_count == 3
    assert prompt_input.target_stats.active_path_encounter_count == 3
