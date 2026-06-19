from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from figure_chain.errors import register_error_handlers
from figure_chain.routers.system import router
from figure_chain.schemas import (
    SystemDependencyStatusResponse,
    SystemDiagnosticsResponse,
)


class FakeSystemService:
    def diagnostics(self) -> SystemDiagnosticsResponse:
        return SystemDiagnosticsResponse(
            status="degraded",
            dependencies={
                "postgresql": SystemDependencyStatusResponse(
                    status="ok",
                    message=None,
                ),
                "neo4j": SystemDependencyStatusResponse(
                    status="error",
                    message="Neo4j is unavailable",
                ),
            },
            config={
                "database_url": "[REDACTED]",
                "redis_url": "[REDACTED]",
                "ai_provider": "fake",
            },
        )


def make_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)
    app.dependency_overrides.clear()
    from figure_chain.dependencies import get_system_service

    app.dependency_overrides[get_system_service] = lambda: FakeSystemService()
    app.include_router(router)
    return app


def test_system_diagnostics_requires_operator() -> None:
    response = TestClient(make_app()).get("/api/v1/system/diagnostics")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_denied"


def test_system_diagnostics_returns_redacted_summary_for_operator() -> None:
    response = TestClient(make_app()).get(
        "/api/v1/system/diagnostics",
        headers={"x-figure-actor": "ops", "x-figure-role": "operator"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["config"]["database_url"] == "[REDACTED]"
    assert "postgresql://" not in response.text
    assert "secret" not in response.text
