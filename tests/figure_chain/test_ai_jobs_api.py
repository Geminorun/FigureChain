from datetime import UTC, datetime
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_ai_jobs_service
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    AiJobCreateRequest,
    AiJobEventListResponse,
    AiJobEventResponse,
    AiJobHealthResponse,
    AiJobListResponse,
    AiJobResponse,
)

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

    def cancel_job(self, job_id: UUID, *, cancelled_by: str) -> AiJobResponse:
        assert job_id == JOB_ID
        assert cancelled_by == "lyl"
        return _job(status="cancelled")

    def retry_job(self, job_id: UUID, *, created_by: str) -> AiJobResponse:
        assert job_id == JOB_ID
        assert created_by == "lyl"
        return _job()

    def list_job_events(self, job_id: UUID) -> AiJobEventListResponse:
        assert job_id == JOB_ID
        now = datetime(2026, 6, 18, tzinfo=UTC)
        return AiJobEventListResponse(
            items=[
                AiJobEventResponse(
                    id=UUID("00000000-0000-0000-0000-000000000601"),
                    job_id=JOB_ID,
                    event_type="created",
                    actor="api",
                    message="AI job created",
                    metadata={"job_type": "candidate_review_suggestion"},
                    created_at=now,
                )
            ],
            count=1,
        )

    def get_queue_health(self, *, stale_after_seconds: int = 300) -> AiJobHealthResponse:
        assert stale_after_seconds == 300
        return AiJobHealthResponse(
            status_counts={"queued": 1},
            queued_count=1,
            running_count=0,
            succeeded_count=0,
            failed_count=0,
            cancelled_count=0,
            stale_running_count=0,
            oldest_queued_at=datetime(2026, 6, 18, tzinfo=UTC),
        )


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
    body = response.json()
    assert body["id"] == str(JOB_ID)
    assert body["queue_backend"] == "database"
    assert body["attempt_count"] == 0


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


def test_cancel_ai_job_endpoint() -> None:
    service = FakeAIJobsService()
    app = _app(service)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ai/jobs/{JOB_ID}/cancel",
            json={"cancelled_by": "lyl"},
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(JOB_ID)
    assert response.json()["status"] == "cancelled"


def test_retry_ai_job_endpoint() -> None:
    service = FakeAIJobsService()
    app = _app(service)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ai/jobs/{JOB_ID}/retry",
            json={"created_by": "lyl"},
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(JOB_ID)


def test_list_ai_job_events_endpoint() -> None:
    app = _app(FakeAIJobsService())

    with TestClient(app) as client:
        response = client.get(f"/api/v1/ai/jobs/{JOB_ID}/events")

    assert response.status_code == 200
    assert response.json()["items"][0]["event_type"] == "created"


def test_ai_job_health_endpoint() -> None:
    app = _app(FakeAIJobsService())

    with TestClient(app) as client:
        response = client.get("/api/v1/ai/health")

    assert response.status_code == 200
    assert response.json()["queued_count"] == 1


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


def _job(*, status: str = "queued") -> AiJobResponse:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return AiJobResponse(
        id=JOB_ID,
        job_type="candidate_review_suggestion",
        target_type="candidate",
        target_kind="relationship",
        target_id=960698,
        status=status,
        created_by="lyl",
        params={"retrieval_limit": 3},
        result_ref_type=None,
        result_ref_id=None,
        error_code=None,
        error_message=None,
        queue_backend="database",
        queue_name=None,
        queue_job_id=None,
        enqueued_at=None,
        attempt_count=0,
        max_attempts=3,
        next_run_at=None,
        cancel_requested_at=None,
        worker_id=None,
        heartbeat_at=None,
        started_at=None,
        finished_at=None,
        created_at=now,
        updated_at=now,
    )
