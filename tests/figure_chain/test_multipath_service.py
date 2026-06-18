from typing import cast
from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    ChainEndpointRequest,
    MultiPathChainRequest,
    MultiPathFiltersRequest,
)
from figure_chain.services.chains import ChainService
from figure_data.graph.pathfinding import ChainEndpointInput
from figure_data.graph.types import MultiPathFilters, MultiPathLookupResult, ResolvedEndpoint


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


def test_chain_service_rejects_same_multipath_endpoint() -> None:
    def resolve_fn(pg_session: Session, endpoint: ChainEndpointInput) -> ResolvedEndpoint:
        return ResolvedEndpoint(
            label=endpoint.label,
            person_id="38966b03-8aa7-5143-8021-2d266889b6c5",
        )

    service = ChainService(
        cast(Session, object()),
        object(),
        resolve_endpoint_fn=resolve_fn,
    )

    try:
        service.multipath(
            MultiPathChainRequest(
                source=ChainEndpointRequest(
                    person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5")
                ),
                target=ChainEndpointRequest(
                    person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5")
                ),
            )
        )
    except ApplicationError as exc:
        assert exc.code is ErrorCode.SAME_PERSON_ENDPOINT
    else:
        raise AssertionError("same multipath endpoint should fail")


def test_chain_service_rejects_excluded_source_or_target_person() -> None:
    endpoints = {
        "source": ResolvedEndpoint(
            label="source",
            person_id="38966b03-8aa7-5143-8021-2d266889b6c5",
        ),
        "target": ResolvedEndpoint(
            label="target",
            person_id="46cfdf66-08c4-5876-964b-4a95d098afe9",
        ),
    }

    def resolve_fn(pg_session: Session, endpoint: ChainEndpointInput) -> ResolvedEndpoint:
        return endpoints[endpoint.label]

    service = ChainService(
        cast(Session, object()),
        object(),
        resolve_endpoint_fn=resolve_fn,
    )

    try:
        service.multipath(
            MultiPathChainRequest(
                source=ChainEndpointRequest(
                    person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5")
                ),
                target=ChainEndpointRequest(
                    person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9")
                ),
                filters=MultiPathFiltersRequest(
                    exclude_person_ids=[
                        UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
                    ],
                ),
            )
        )
    except ApplicationError as exc:
        assert exc.code is ErrorCode.PATH_FILTER_INVALID
        assert exc.details == {
            "excluded_endpoint_person_ids": ["38966b03-8aa7-5143-8021-2d266889b6c5"],
        }
    else:
        raise AssertionError("excluding source or target person should fail")
