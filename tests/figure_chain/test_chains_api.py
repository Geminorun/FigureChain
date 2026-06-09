from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable
from pytest import raises
from sqlalchemy.orm import Session

from figure_chain.app import create_app
from figure_chain.dependencies import get_chain_service
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    ChainEdgeResponse,
    ChainEndpointRequest,
    ChainPathResponse,
    ChainPersonResponse,
    ShortestChainRequest,
    ShortestChainResponse,
)
from figure_chain.services.chains import ChainService
from figure_data.graph.pathfinding import ChainEndpointInput
from figure_data.graph.types import ChainLookupResult, GraphPersonAmbiguousError, ResolvedEndpoint


class FakeChainService:
    def shortest(self, request: ShortestChainRequest) -> ShortestChainResponse:
        if request.source.query == "多人":
            raise ApplicationError(
                code=ErrorCode.PERSON_AMBIGUOUS,
                message="source matched multiple people",
                details={"endpoint": "source", "candidates": ["person-1", "person-2"]},
            )
        if request.source.query == "无路":
            return ShortestChainResponse(
                status="no_path",
                source_person_id="person-a",
                target_person_id="person-b",
                max_depth=request.max_depth,
                path=None,
            )
        return ShortestChainResponse(
            status="found",
            source_person_id="38966b03-8aa7-5143-8021-2d266889b6c5",
            target_person_id="46cfdf66-08c4-5876-964b-4a95d098afe9",
            max_depth=request.max_depth,
            path=ChainPathResponse(
                length=1,
                people=[
                    ChainPersonResponse(
                        person_id="38966b03-8aa7-5143-8021-2d266889b6c5",
                        display_name="許幾",
                        birth_year=1054,
                        death_year=1115,
                        cbdb_external_id="780",
                    ),
                    ChainPersonResponse(
                        person_id="46cfdf66-08c4-5876-964b-4a95d098afe9",
                        display_name="韓琦",
                        birth_year=1008,
                        death_year=1075,
                        cbdb_external_id="630",
                    ),
                ],
                edges=[
                    ChainEdgeResponse(
                        encounter_id="e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                        encounter_kind="direct_interaction",
                        certainty_level="high",
                        pages="11905",
                        evidence_summary="许几谒韩琦于魏",
                    )
                ],
            ),
        )


def test_shortest_chain_found() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_chain_service] = lambda: FakeChainService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/shortest",
            json={
                "source": {"person_id": "38966b03-8aa7-5143-8021-2d266889b6c5"},
                "target": {"person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9"},
                "max_depth": 12,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "found"
    assert body["path"]["length"] == 1
    assert body["path"]["edges"][0]["encounter_id"] == "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"


def test_shortest_chain_no_path_returns_200() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_chain_service] = lambda: FakeChainService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/shortest",
            json={"source": {"query": "无路"}, "target": {"query": "韓琦"}},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "no_path"
    assert response.json()["path"] is None


def test_shortest_chain_ambiguous_returns_409() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_chain_service] = lambda: FakeChainService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/shortest",
            json={"source": {"query": "多人"}, "target": {"query": "韓琦"}},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "person_ambiguous"


def test_shortest_chain_dependency_unavailable_returns_503() -> None:
    class UnavailableChainService:
        def shortest(self, request: ShortestChainRequest) -> ShortestChainResponse:
            raise ApplicationError(
                code=ErrorCode.DEPENDENCY_UNAVAILABLE,
                message="Neo4j is unavailable; check NEO4J_URI and service status",
            )

    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_chain_service] = lambda: UnavailableChainService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/shortest",
            json={"source": {"query": "許幾"}, "target": {"query": "韓琦"}},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"


def test_shortest_chain_rejects_too_deep_request() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_chain_service] = lambda: FakeChainService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/shortest",
            json={"source": {"query": "許幾"}, "target": {"query": "韓琦"}, "max_depth": 31},
        )

    assert response.status_code == 422


def test_chain_service_rejects_same_person_after_resolution() -> None:
    def resolve_same_person(
        pg_session: Session,
        endpoint: ChainEndpointInput,
    ) -> ResolvedEndpoint:
        return ResolvedEndpoint(label=endpoint.label, person_id="same-person")

    def find_chain_should_not_run(
        pg_session: Session,
        neo4j_session: object,
        source: ChainEndpointInput,
        target: ChainEndpointInput,
        max_depth: int,
    ) -> ChainLookupResult:
        raise AssertionError("find_chain should not run for same-person endpoints")

    service = ChainService(
        cast(Session, object()),
        object(),
        find_chain_fn=find_chain_should_not_run,
        resolve_endpoint_fn=resolve_same_person,
    )

    with raises(ApplicationError) as exc_info:
        service.shortest(
            ShortestChainRequest(
                source=ChainEndpointRequest(query="許幾"),
                target=ChainEndpointRequest(query="許幾"),
            )
        )

    assert exc_info.value.code is ErrorCode.SAME_PERSON_ENDPOINT


def test_chain_service_maps_neo4j_unavailable_to_dependency_error() -> None:
    def resolve_endpoint(
        pg_session: Session,
        endpoint: ChainEndpointInput,
    ) -> ResolvedEndpoint:
        return ResolvedEndpoint(label=endpoint.label, person_id=f"{endpoint.label}-person")

    def find_chain_unavailable(
        pg_session: Session,
        neo4j_session: object,
        source: ChainEndpointInput,
        target: ChainEndpointInput,
        max_depth: int,
    ) -> ChainLookupResult:
        raise ServiceUnavailable("Neo4j is unavailable")

    service = ChainService(
        cast(Session, object()),
        object(),
        find_chain_fn=find_chain_unavailable,
        resolve_endpoint_fn=resolve_endpoint,
    )

    with raises(ApplicationError) as exc_info:
        service.shortest(
            ShortestChainRequest(
                source=ChainEndpointRequest(query="許幾"),
                target=ChainEndpointRequest(query="韓琦"),
            )
        )

    assert exc_info.value.code is ErrorCode.DEPENDENCY_UNAVAILABLE
    assert "Neo4j is unavailable" in exc_info.value.message


def test_chain_service_preserves_ambiguous_candidate_details() -> None:
    def resolve_endpoint(
        pg_session: Session,
        endpoint: ChainEndpointInput,
    ) -> ResolvedEndpoint:
        if endpoint.label == "source":
            raise GraphPersonAmbiguousError(
                label=endpoint.label,
                candidates=["person-1", "person-2"],
            )
        return ResolvedEndpoint(label=endpoint.label, person_id="target-person")

    def find_chain_should_not_run(
        pg_session: Session,
        neo4j_session: object,
        source: ChainEndpointInput,
        target: ChainEndpointInput,
        max_depth: int,
    ) -> ChainLookupResult:
        raise AssertionError("find_chain should not run for ambiguous endpoints")

    service = ChainService(
        cast(Session, object()),
        object(),
        find_chain_fn=find_chain_should_not_run,
        resolve_endpoint_fn=resolve_endpoint,
    )

    with raises(ApplicationError) as exc_info:
        service.shortest(
            ShortestChainRequest(
                source=ChainEndpointRequest(query="王"),
                target=ChainEndpointRequest(query="韓琦"),
            )
        )

    assert exc_info.value.code is ErrorCode.PERSON_AMBIGUOUS
    assert exc_info.value.details == {
        "endpoint": "source",
        "candidates": ["person-1", "person-2"],
    }
