from uuid import UUID

import pytest
from pydantic import ValidationError

from figure_chain.schemas import (
    ChainEndpointRequest,
    MultiPathChainRequest,
    MultiPathChainResponse,
    MultiPathFiltersRequest,
    MultiPathItemResponse,
)


SOURCE_ID = UUID("38966b03-8aa7-5143-8021-2d266889b6c5")
TARGET_ID = UUID("46cfdf66-08c4-5876-964b-4a95d098afe9")


def test_multipath_request_defaults_are_safe() -> None:
    request = MultiPathChainRequest(
        source=ChainEndpointRequest(person_id=SOURCE_ID),
        target=ChainEndpointRequest(person_id=TARGET_ID),
    )

    assert request.max_depth == 12
    assert request.max_paths == 5
    assert request.extra_depth == 0
    assert request.filters.min_certainty_level == "high"
    assert request.filters.encounter_kinds == []
    assert request.filters.exclude_person_ids == []
    assert request.filters.exclude_encounter_ids == []


def test_multipath_request_bounds() -> None:
    with pytest.raises(ValidationError):
        MultiPathChainRequest(
            source=ChainEndpointRequest(person_id=SOURCE_ID),
            target=ChainEndpointRequest(person_id=TARGET_ID),
            max_depth=21,
        )

    with pytest.raises(ValidationError):
        MultiPathChainRequest(
            source=ChainEndpointRequest(person_id=SOURCE_ID),
            target=ChainEndpointRequest(person_id=TARGET_ID),
            max_paths=0,
        )

    with pytest.raises(ValidationError):
        MultiPathChainRequest(
            source=ChainEndpointRequest(person_id=SOURCE_ID),
            target=ChainEndpointRequest(person_id=TARGET_ID),
            extra_depth=3,
        )


def test_multipath_filters_accept_supported_values() -> None:
    filters = MultiPathFiltersRequest(
        min_certainty_level="medium",
        encounter_kinds=["direct_interaction", "family_contact"],
        source_work_ids=[1, 2],
        intermediate_dynasty_codes=[15],
        intermediate_year_min=900,
        intermediate_year_max=1200,
    )

    assert filters.min_certainty_level == "medium"
    assert filters.encounter_kinds == ["direct_interaction", "family_contact"]
    assert filters.source_work_ids == [1, 2]


def test_multipath_response_supports_found_and_no_path() -> None:
    found = MultiPathChainResponse(
        status="found",
        source_person_id=str(SOURCE_ID),
        target_person_id=str(TARGET_ID),
        max_depth=12,
        max_paths=5,
        extra_depth=1,
        shortest_length=2,
        returned_paths=1,
        filters_applied=MultiPathFiltersRequest(),
        paths=[
            MultiPathItemResponse(
                path_id="path-1",
                rank=1,
                chain_hash="sha256:test",
                length=2,
                quality_score=1.0,
                people=[],
                edges=[],
            )
        ],
    )
    no_path = MultiPathChainResponse(
        status="no_path",
        source_person_id=str(SOURCE_ID),
        target_person_id=str(TARGET_ID),
        max_depth=12,
        max_paths=5,
        extra_depth=0,
        shortest_length=None,
        returned_paths=0,
        filters_applied=MultiPathFiltersRequest(),
        paths=[],
    )

    assert found.status == "found"
    assert found.returned_paths == 1
    assert no_path.status == "no_path"
    assert no_path.paths == []
