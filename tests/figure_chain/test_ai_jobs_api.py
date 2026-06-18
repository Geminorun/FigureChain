from datetime import UTC, datetime
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_ai_jobs_service
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import AiJobCreateRequest, AiJobListResponse, AiJobResponse

JOB_ID = UUID("00000000-0000-0000-0000-000000000501")


class FakeAIJobsService:
    def __init__(self) -> None:
        self.created_request: AiJobCreateRequest | None = None

    def create_job(self, request: AiJobCreateRequest) -> AiJobResponse:
        self.created_request = request
        if request.job_type == "unknown":
            raise ApplicationError(
                code=ErrorCode.AI_JOB_INVALID_TYPE,
                message="AI job type is not supported",
                details={"job_type": request.job_type},
            )
        return _job()

    def get_job(self, job_id: UUID) -> AiJobResponse:
        assert job_id == JOB_ID
        return _job()

    def list_jobs(
        self,
        *,
        target_type: str,
        target_kind: str,
        target_id: int,
        limit: int,
    ) -> AiJobListResponse:
        assert target_type == "candidate"
        assert target_kind == "relationship"
        assert target_id == 960698
        assert limit == 10
        return AiJobListResponse(items=[_job()], count=1, limit=limit)


def test_create_ai_job_returns_queued_job() -> None:
    service = FakeAIJobsService()
    app = _app(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/jobs",
            json={
                "job_type": "candidate_review_suggestion",
                "target_type": "candidate",
                "target_kind": "relationship",
                "target_id": 960698,
                "created_by": "lyl",
                "params": {"retrieval_limit": 3},
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(JOB_ID)
    assert body["status"] == "queued"
    assert service.created_request is not None
    assert service.created_request.params == {"retrieval_limit": 3}


def test_get_ai_job_returns_job() -> None:
    app = _app(FakeAIJobsService())

    with TestClient(app) as client:
        response = client.get(f"/api/v1/ai/jobs/{JOB_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(JOB_ID)


def test_list_ai_jobs_returns_target_history() -> None:
    app = _app(FakeAIJobsService())

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ai/jobs",
            params={
                "target_type": "candidate",
                "target_kind": "relationship",
                "target_id": "960698",
                "limit": "10",
            },
        )

    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_create_ai_job_returns_stable_invalid_type_error() -> None:
    app = _app(FakeAIJobsService())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/jobs",
            json={
                "job_type": "unknown",
                "target_type": "candidate",
                "target_kind": "relationship",
                "target_id": 960698,
                "created_by": "lyl",
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ai_job_invalid_type"


def _app(service: FakeAIJobsService) -> FastAPI:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_ai_jobs_service] = lambda: service
    return app


def _job() -> AiJobResponse:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return AiJobResponse(
        id=JOB_ID,
        job_type="candidate_review_suggestion",
        target_type="candidate",
        target_kind="relationship",
        target_id=960698,
        status="queued",
        created_by="lyl",
        params={"retrieval_limit": 3},
        result_ref_type=None,
        result_ref_id=None,
        error_code=None,
        error_message=None,
        started_at=None,
        finished_at=None,
        created_at=now,
        updated_at=now,
    )
