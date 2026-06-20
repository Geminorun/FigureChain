from collections.abc import Generator
from typing import Any, cast
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from figure_chain.app import create_app
from figure_chain.dependencies import get_pg_session


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
    assert "/api/v1/ai/jobs" in route_paths
    assert "/api/v1/ai/jobs/{job_id}" in route_paths
    assert "/api/v1/admin/operations" in route_paths
    assert "/api/v1/admin/operations/{operation_id}" in route_paths
    assert "/api/v1/admin/resources" in route_paths
    assert "/api/v1/admin/resources/query" in route_paths
    assert "/api/v1/admin/graph/status" in route_paths
    assert "/api/v1/admin/graph/validate-encounters" in route_paths
    assert "/api/v1/admin/graph/sync" in route_paths
    assert "/api/v1/admin/graph/validate-graph" in route_paths
    assert "/api/v1/admin/ai/health" in route_paths
    assert "/api/v1/admin/ai/jobs" in route_paths
    assert "/api/v1/admin/ai/jobs/requeue" in route_paths
    assert "/api/v1/admin/ai/jobs/{job_id}" in route_paths
    assert "/api/v1/admin/ai/jobs/{job_id}/events" in route_paths
    assert "/api/v1/admin/ai/jobs/{job_id}/cancel" in route_paths
    assert "/api/v1/admin/ai/jobs/{job_id}/retry" in route_paths
    assert "/api/v1/admin/review/candidates" in route_paths
    assert "/api/v1/admin/review/candidates/{kind}/{candidate_id}" in route_paths
    assert "/api/v1/admin/review/candidates/{kind}/{candidate_id}/promote" in route_paths
    assert "/api/v1/admin/review/candidates/{kind}/{candidate_id}/reject" in route_paths
    assert "/api/v1/admin/review/candidates/{kind}/{candidate_id}/needs-review" in route_paths
    assert "/api/v1/admin/review/encounters/{encounter_id}/retract" in route_paths
    assert "/api/v1/review/candidates" in route_paths
    assert "/api/v1/review/candidates/{kind}/{candidate_id}" in route_paths


def test_pg_session_dependency_commits_successful_request() -> None:
    session = Mock(spec=Session)
    request = cast(Any, _request_with_session(session))
    dependency = cast(Generator[Session, None, None], get_pg_session(request))

    assert next(dependency) is session

    try:
        next(dependency)
    except StopIteration:
        pass

    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()
    session.close.assert_called_once_with()


def test_pg_session_dependency_rolls_back_failed_request() -> None:
    session = Mock(spec=Session)
    request = cast(Any, _request_with_session(session))
    dependency = cast(Generator[Session, None, None], get_pg_session(request))

    assert next(dependency) is session

    try:
        dependency.throw(RuntimeError("boom"))
    except RuntimeError:
        pass

    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()


def _request_with_session(session: Mock) -> object:
    class State:
        pg_session_factory = staticmethod(lambda: session)

    class App:
        state = State()

    class Request:
        app = App()

    return Request()
