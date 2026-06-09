from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_health_service
from figure_chain.schemas import DependencyStatusResponse, ReadyResponse


class ReadyHealthService:
    def readiness(self) -> ReadyResponse:
        return ReadyResponse(
            status="ready",
            dependencies={
                "postgresql": DependencyStatusResponse(status="ok"),
                "neo4j": DependencyStatusResponse(status="ok"),
            },
        )


class NotReadyHealthService:
    def readiness(self) -> ReadyResponse:
        return ReadyResponse(
            status="not_ready",
            dependencies={
                "postgresql": DependencyStatusResponse(status="ok"),
                "neo4j": DependencyStatusResponse(status="error", message="Neo4j is unavailable"),
            },
        )


def test_ready_health_returns_200() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_health_service] = lambda: ReadyHealthService()

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_not_ready_health_returns_503() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_health_service] = lambda: NotReadyHealthService()

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["dependencies"]["neo4j"]["message"] == "Neo4j is unavailable"
