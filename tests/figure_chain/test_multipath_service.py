from typing import cast
from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.schemas import ChainEndpointRequest, MultiPathChainRequest
from figure_chain.services.chains import ChainService
from figure_data.graph.pathfinding import ChainEndpointInput
from figure_data.graph.types import MultiPathFilters, MultiPathLookupResult


def test_chain_service_maps_multipath_no_path() -> None:
    def find_fn(
        pg_session: Session,
        neo4j_session: object,
        source: ChainEndpointInput,
        target: ChainEndpointInput,
        max_depth: int,
        max_paths: int,
        extra_depth: int,
        filters: MultiPathFilters,
    ) -> MultiPathLookupResult:
        return MultiPathLookupResult(
            source_person_id="source",
            target_person_id="target",
            max_depth=max_depth,
            max_paths=max_paths,
            extra_depth=extra_depth,
            filters=filters,
            shortest_length=None,
            paths=(),
        )

    service = ChainService(
        cast(Session, object()),
        object(),
        find_multipath_fn=find_fn,
    )
    response = service.multipath(
        MultiPathChainRequest(
            source=ChainEndpointRequest(person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5")),
            target=ChainEndpointRequest(person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9")),
        )
    )

    assert response.status == "no_path"
    assert response.paths == []
