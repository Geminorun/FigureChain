from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from figure_chain.errors import ApplicationError, ErrorCode, register_error_handlers
from figure_chain.schemas import ChainEndpointRequest, ShortestChainRequest, display_name


def test_chain_endpoint_requires_exactly_one_locator() -> None:
    endpoint = ChainEndpointRequest(person_id=UUID("00000000-0000-0000-0000-000000000001"))

    assert endpoint.person_id == UUID("00000000-0000-0000-0000-000000000001")

    try:
        ChainEndpointRequest()
    except ValidationError as exc:
        assert "exactly one locator" in str(exc)
    else:
        raise AssertionError("empty endpoint should fail")

    try:
        ChainEndpointRequest(
            person_id=UUID("00000000-0000-0000-0000-000000000001"),
            cbdb_id="780",
        )
    except ValidationError as exc:
        assert "exactly one locator" in str(exc)
    else:
        raise AssertionError("multi-locator endpoint should fail")


def test_shortest_chain_request_defaults_max_depth() -> None:
    request = ShortestChainRequest(
        source=ChainEndpointRequest(cbdb_id="780"),
        target=ChainEndpointRequest(query="韓琦"),
    )

    assert request.max_depth == 12


def test_display_name_prefers_hant_then_hans_then_romanized() -> None:
    assert display_name("許幾", "许几", "Xu Ji", "person-id") == "許幾"
    assert display_name(None, "许几", "Xu Ji", "person-id") == "许几"
    assert display_name(None, None, "Xu Ji", "person-id") == "Xu Ji"
    assert display_name(None, None, None, "person-id") == "person-id"


def test_application_error_handler_returns_stable_shape() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise ApplicationError(
            code=ErrorCode.PERSON_NOT_FOUND,
            message="source person was not found",
            details={"endpoint": "source"},
        )

    with TestClient(app) as client:
        response = client.get("/boom")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "person_not_found",
            "message": "source person was not found",
            "details": {"endpoint": "source"},
        }
    }
