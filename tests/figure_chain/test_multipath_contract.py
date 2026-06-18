from uuid import UUID

from figure_chain.schemas import (
    ChainEndpointRequest,
    MultiPathChainRequest,
    MultiPathFiltersRequest,
)
from figure_chain.services.chains import multipath_filters_from_request
from figure_data.graph.types import MultiPathFilters


def test_multipath_filters_from_request_normalizes_uuid_lists() -> None:
    request = MultiPathChainRequest(
        source=ChainEndpointRequest(person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5")),
        target=ChainEndpointRequest(person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9")),
        filters=MultiPathFiltersRequest(
            min_certainty_level="medium",
            encounter_kinds=["direct_interaction"],
            exclude_person_ids=[UUID("00000000-0000-0000-0000-000000000001")],
            exclude_encounter_ids=[UUID("00000000-0000-0000-0000-000000000002")],
            source_work_ids=[7596],
            intermediate_dynasty_codes=[15],
            intermediate_year_min=900,
            intermediate_year_max=1200,
        ),
    )

    filters = multipath_filters_from_request(request)

    assert filters == MultiPathFilters(
        min_certainty_level="medium",
        encounter_kinds=("direct_interaction",),
        exclude_person_ids=("00000000-0000-0000-0000-000000000001",),
        exclude_encounter_ids=("00000000-0000-0000-0000-000000000002",),
        source_work_ids=(7596,),
        intermediate_dynasty_codes=(15,),
        intermediate_year_min=900,
        intermediate_year_max=1200,
    )
