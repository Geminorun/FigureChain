from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_chain_service
from figure_chain.schemas import (
    MultiPathChainRequest,
    MultiPathChainResponse,
    MultiPathFiltersRequest,
)


class FakeChainService:
    def multipath(self, request: MultiPathChainRequest) -> MultiPathChainResponse:
        return MultiPathChainResponse(
            status="no_path",
            source_person_id="source",
            target_person_id="target",
            max_depth=request.max_depth,
            max_paths=request.max_paths,
            extra_depth=request.extra_depth,
            shortest_length=None,
            returned_paths=0,
            paths=[],
            filters_applied=MultiPathFiltersRequest(),
        )


def test_multipath_route_returns_no_path() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_chain_service] = lambda: FakeChainService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/multipath",
            json={
                "source": {"person_id": "38966b03-8aa7-5143-8021-2d266889b6c5"},
                "target": {"person_id": "46cfdf66-08c4-5876-964b-4a95d098afe9"},
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "no_path"
