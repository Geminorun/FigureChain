from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from figure_chain.access import OperationContext
from figure_chain.dependencies import (
    get_operation_context,
    require_operator_context,
    require_reviewer_context,
)
from figure_chain.errors import register_error_handlers


def make_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/context")
    def context_route(
        context: Annotated[OperationContext, Depends(get_operation_context)],
    ) -> dict[str, str]:
        return {"actor_id": context.actor_id, "role": context.role.value}

    @app.post("/reviewer")
    def reviewer_route(
        context: Annotated[OperationContext, Depends(require_reviewer_context)],
    ) -> dict[str, str]:
        return {"role": context.role.value}

    @app.post("/operator")
    def operator_route(
        context: Annotated[OperationContext, Depends(require_operator_context)],
    ) -> dict[str, str]:
        return {"role": context.role.value}

    return app


def test_operation_context_defaults_to_explorer() -> None:
    response = TestClient(make_app()).get("/context")

    assert response.status_code == 200
    assert response.json() == {"actor_id": "anonymous", "role": "explorer"}


def test_reviewer_header_allows_reviewer_route() -> None:
    response = TestClient(make_app()).post(
        "/reviewer",
        headers={"x-figure-actor": "alice", "x-figure-role": "reviewer"},
    )

    assert response.status_code == 200
    assert response.json() == {"role": "reviewer"}


def test_explorer_header_rejects_operator_route() -> None:
    response = TestClient(make_app()).post(
        "/operator",
        headers={"x-figure-actor": "guest", "x-figure-role": "explorer"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_denied"


def test_unknown_role_falls_back_to_explorer() -> None:
    response = TestClient(make_app()).get(
        "/context",
        headers={"x-figure-actor": "bob", "x-figure-role": "admin"},
    )

    assert response.status_code == 200
    assert response.json() == {"actor_id": "bob", "role": "explorer"}
