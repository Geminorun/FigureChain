from fastapi.testclient import TestClient

from figure_chain.app import create_app


def test_create_app_exposes_live_health() -> None:
    app = create_app(lifespan_enabled=False)

    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "alive",
        "service": "figure-chain-api",
    }


def test_create_app_registers_api_prefix_routes_after_startup() -> None:
    app = create_app(lifespan_enabled=False)

    route_paths = {getattr(route, "path", None) for route in app.routes}

    assert "/health/live" in route_paths
