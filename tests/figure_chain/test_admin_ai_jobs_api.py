from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from httpx import Response

from figure_chain.app import create_app
from figure_chain.dependencies import get_admin_ai_jobs_service
from figure_chain.schemas import (
    AdminAIJobActionResponse,
    AdminAIJobListResponse,
    AiJobEventListResponse,
    AiJobEventResponse,
    AiJobHealthResponse,
    AiJobResponse,
)

JOB_ID = UUID("00000000-0000-0000-0000-000000000801")
OPERATION_ID = UUID("00000000-0000-0000-0000-000000000901")
NOW = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
OPERATOR_HEADERS = {"x-figure-role": "operator", "x-figure-actor": "local"}


class FakeAdminAIJobsService:
    def list_jobs(
        self,
        *,
        status: str | None = None,
        target_kind: str | None = None,
        target_id: int | None = None,
        queue_backend: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AdminAIJobListResponse:
        return AdminAIJobListResponse(
            items=[_job_response(id=JOB_ID, status=status or "queued")],
            count=1,
            limit=limit,
            offset=offset,
        )

    def get_job(self, job_id: UUID) -> AiJobResponse:
        return _job_response(id=job_id)

    def list_job_events(self, job_id: UUID) -> AiJobEventListResponse:
        return AiJobEventListResponse(
            items=[
                AiJobEventResponse(
                    id=uuid4(),
                    job_id=job_id,
                    event_type="created",
                    actor="api",
                    message="AI job created",
                    metadata={},
                    created_at=NOW,
                )
            ],
            count=1,
        )

    def cancel_job(self, job_id: UUID, request: object) -> AdminAIJobActionResponse:
        return _action("cancel_ai_job", _job_response(id=job_id, status="cancelled"))

    def retry_job(self, job_id: UUID, request: object) -> AdminAIJobActionResponse:
        return _action("retry_ai_job", _job_response(id=uuid4(), status="queued"))

    def requeue_jobs(self, request: object) -> AdminAIJobActionResponse:
        return _action("requeue_ai_jobs", None)

    def get_health(self) -> AiJobHealthResponse:
        return AiJobHealthResponse(
            status_counts={"queued": 1},
            queued_count=1,
            running_count=0,
            succeeded_count=0,
            failed_count=0,
            cancelled_count=0,
            stale_running_count=0,
            oldest_queued_at=NOW,
        )


def test_admin_ai_jobs_api_requires_operator_role() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_ai_jobs_service] = lambda: FakeAdminAIJobsService()
    try:
        response = TestClient(app).get(
            "/api/v1/admin/ai/jobs",
            headers={"x-figure-role": "reviewer"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_admin_ai_jobs_api_lists_jobs() -> None:
    response = _get("/api/v1/admin/ai/jobs?status=queued&limit=10&offset=5")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["items"][0]["status"] == "queued"
    assert response.json()["limit"] == 10
    assert response.json()["offset"] == 5


def test_admin_ai_jobs_api_gets_job_detail() -> None:
    response = _get(f"/api/v1/admin/ai/jobs/{JOB_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(JOB_ID)


def test_admin_ai_jobs_api_lists_events() -> None:
    response = _get(f"/api/v1/admin/ai/jobs/{JOB_ID}/events")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["items"][0]["event_type"] == "created"


def test_admin_ai_jobs_api_cancels_job() -> None:
    response = _post(f"/api/v1/admin/ai/jobs/{JOB_ID}/cancel", {"actor": "operator"})

    assert response.status_code == 200
    assert response.json()["operation_type"] == "cancel_ai_job"
    assert response.json()["operation_id"] == str(OPERATION_ID)


def test_admin_ai_jobs_api_retries_job() -> None:
    response = _post(f"/api/v1/admin/ai/jobs/{JOB_ID}/retry", {"actor": "operator"})

    assert response.status_code == 200
    assert response.json()["operation_type"] == "retry_ai_job"


def test_admin_ai_jobs_api_requeues_jobs() -> None:
    response = _post("/api/v1/admin/ai/jobs/requeue", {"actor": "operator", "limit": 10})

    assert response.status_code == 200
    assert response.json()["operation_type"] == "requeue_ai_jobs"


def test_admin_ai_jobs_api_gets_health() -> None:
    response = _get("/api/v1/admin/ai/health")

    assert response.status_code == 200
    assert response.json()["queued_count"] == 1


def _get(path: str) -> Response:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_ai_jobs_service] = lambda: FakeAdminAIJobsService()
    try:
        return TestClient(app).get(path, headers=OPERATOR_HEADERS)
    finally:
        app.dependency_overrides.clear()


def _post(path: str, body: dict[str, object]) -> Response:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_admin_ai_jobs_service] = lambda: FakeAdminAIJobsService()
    try:
        return TestClient(app).post(path, headers=OPERATOR_HEADERS, json=body)
    finally:
        app.dependency_overrides.clear()


def _action(operation_type: str, job: AiJobResponse | None) -> AdminAIJobActionResponse:
    return AdminAIJobActionResponse(
        operation_id=OPERATION_ID,
        operation_type=operation_type,
        status="succeeded",
        job=job,
        result_summary={},
        preview=f"figure-data {operation_type}",
    )


def _job_response(*, id: UUID, status: str = "queued") -> AiJobResponse:
    return AiJobResponse(
        id=id,
        job_type="candidate_review_suggestion",
        target_type="candidate",
        target_kind="relationship",
        target_id=1,
        status=status,
        created_by="local",
        params={},
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
        created_at=NOW,
        updated_at=NOW,
    )
