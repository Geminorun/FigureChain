from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from figure_chain.errors import ERROR_STATUS, ApplicationError, ErrorCode, register_error_handlers
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


def test_review_candidate_error_codes_have_stable_http_statuses() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/missing-candidate")
    def missing_candidate() -> None:
        raise ApplicationError(
            code=ErrorCode.CANDIDATE_NOT_FOUND,
            message="candidate was not found",
        )

    @app.get("/invalid-kind")
    def invalid_kind() -> None:
        raise ApplicationError(
            code=ErrorCode.CANDIDATE_INVALID_KIND,
            message="candidate kind is not supported",
            details={"kind": "invalid"},
        )

    with TestClient(app) as client:
        missing_response = client.get("/missing-candidate")
        invalid_response = client.get("/invalid-kind")

    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "candidate_not_found"
    assert invalid_response.status_code == 400
    assert invalid_response.json() == {
        "error": {
            "code": "candidate_invalid_kind",
            "message": "candidate kind is not supported",
            "details": {"kind": "invalid"},
        }
    }


def test_multipath_error_codes_have_status_mapping() -> None:
    assert ErrorCode.PATH_FILTER_INVALID.value == "path_filter_invalid"
    assert ErrorCode.PATH_QUERY_TOO_BROAD.value == "path_query_too_broad"
    assert ERROR_STATUS[ErrorCode.PATH_FILTER_INVALID] == 400
    assert ERROR_STATUS[ErrorCode.PATH_QUERY_TOO_BROAD] == 400


def test_access_denied_maps_to_403() -> None:
    assert ErrorCode.ACCESS_DENIED.value == "access_denied"
    assert ERROR_STATUS[ErrorCode.ACCESS_DENIED] == 403
