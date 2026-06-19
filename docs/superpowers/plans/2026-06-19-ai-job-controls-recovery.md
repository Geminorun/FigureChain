# AI Job Controls and Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cancellation, retry, requeue, rate limiting, health, and event APIs for Redis/RQ-backed AI jobs.

**Architecture:** Keep PostgreSQL as the job control source, use Redis for short-lived rate-limit counters and queue deletion where available, and expose explicit API/CLI controls. User retry creates a new job; maintenance requeue repairs durable queued jobs that were not present in Redis. Automatic retry only uses `running -> queued` with `next_run_at` and a `retry_scheduled` event; `failed -> queued` is a maintenance CLI-only transition that requires explicit operator intent.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Redis, RQ, Typer, pytest, ruff, mypy.

---

## References

- Foundation plan: `docs/superpowers/plans/2026-06-19-redis-rq-ai-jobs-foundation.md`
- Worker plan: `docs/superpowers/plans/2026-06-19-redis-rq-ai-worker.md`
- Spec: `docs/superpowers/specs/2026-06-19-redis-rq-ai-jobs-priority-design.md`

## Prerequisites

Complete and verify both foundation and worker plans before starting. This plan expects `ai_job_events`, queue metadata fields, RQ enqueue, and `execute_ai_job()` to exist.

## File Structure

- Modify `src/figure_data/ai/job_repository.py`: cancellation, retry, requeue, event listing, health queries.
- Modify `src/figure_data/ai/job_runner.py`: retry policy and cancellation checks.
- Create `src/figure_data/ai/job_rate_limit.py`: Redis/fake rate limiter.
- Modify `src/figure_chain/schemas.py`: control request/response schemas and event schemas.
- Modify `src/figure_chain/services/ai_jobs.py`: cancel, retry, events, health.
- Modify `src/figure_chain/routers/ai_jobs.py`: new endpoints.
- Modify `src/figure_data/cli.py`: `cancel-ai-job`.
- Test `tests/ai`, `tests/figure_chain`, and `tests/db`.

### Task 1: Add Repository Controls for Cancel, Retry, Events, and Health

**Files:**
- Modify: `src/figure_data/ai/job_repository.py`
- Test: `tests/ai/test_job_repository.py`

- [ ] **Step 1: Write repository tests**

Add to `tests/ai/test_job_repository.py`:

```python
def test_cancel_queued_job_sets_cancelled_status() -> None:
    session = FakeSession()

    record = cancel_queued_job(
        session,  # type: ignore[arg-type]
        JOB_ID,
        cancelled_by="lyl",
    )

    assert record.status == "cancelled"
    assert session.params[0]["status"] == "cancelled"
    assert "cancel_requested_at = :now" in session.statements[0]


def test_request_running_job_cancel_sets_cancel_requested_at() -> None:
    session = FakeSession()

    record = request_running_job_cancel(
        session,  # type: ignore[arg-type]
        JOB_ID,
        cancelled_by="lyl",
    )

    assert record.id == JOB_ID
    assert "cancel_requested_at = :now" in session.statements[0]


def test_schedule_job_retry_sets_next_run_at() -> None:
    session = FakeSession()

    record = schedule_job_retry(
        session,  # type: ignore[arg-type]
        JOB_ID,
        error_code="provider_timeout",
        error_message="timeout",
        delay_seconds=10,
    )

    assert record.status == "queued"
    assert session.params[0]["error_code"] == "provider_timeout"
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_repository.py -q
```

Expected: fail because repository controls are missing.

- [ ] **Step 3: Implement cancel functions**

Add:

```python
def cancel_queued_job(
    session: Session,
    job_id: UUID,
    *,
    cancelled_by: str,
) -> AIGenerationJobRecord:
    return _transition(
        session,
        job_id=job_id,
        expected_status=AIJobStatus.QUEUED.value,
        new_status=AIJobStatus.CANCELLED.value,
        assignments="cancel_requested_at = :now, finished_at = :now, updated_at = :now",
        extra_params={},
    )
```

Add:

```python
def request_running_job_cancel(
    session: Session,
    job_id: UUID,
    *,
    cancelled_by: str,
) -> AIGenerationJobRecord:
    return _transition(
        session,
        job_id=job_id,
        expected_status=AIJobStatus.RUNNING.value,
        new_status=AIJobStatus.RUNNING.value,
        assignments="cancel_requested_at = :now, updated_at = :now",
        extra_params={},
    )
```

- [ ] **Step 4: Implement retry scheduling**

Add:

```python
def schedule_job_retry(
    session: Session,
    job_id: UUID,
    *,
    error_code: str,
    error_message: str,
    delay_seconds: int,
) -> AIGenerationJobRecord:
    next_run_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
    return _transition(
        session,
        job_id=job_id,
        expected_status=AIJobStatus.RUNNING.value,
        new_status=AIJobStatus.QUEUED.value,
        assignments=(
            "error_code = :error_code, error_message = :error_message, "
            "next_run_at = :next_run_at, updated_at = :now"
        ),
        extra_params={
            "error_code": error_code,
            "error_message": error_message,
            "next_run_at": next_run_at,
        },
    )
```

Import `timedelta`.

- [ ] **Step 5: Implement event list and health query**

Add:

```python
def list_job_events(session: Session, job_id: UUID) -> list[AIJobEventRecord]:
    rows = (
        session.execute(
            text(
                """
                select id, job_id, event_type, actor, message, metadata_json, created_at
                from figure_data.ai_job_events
                where job_id = :job_id
                order by created_at, id
                """
            ),
            {"job_id": job_id},
        )
        .mappings()
        .all()
    )
    return [_event_from_row(cast(Mapping[str, Any], row)) for row in rows]
```

Add `_event_from_row()`.

- [ ] **Step 6: Run repository tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_repository.py -q
```

Expected: pass.

- [ ] **Step 7: Commit Task 1**

```powershell
git add src/figure_data/ai/job_repository.py tests/ai/test_job_repository.py
git commit -m "feat: 增加 AI job 控制仓储"
```

### Task 2: Add Backend Cancel, Retry, Events, and Health APIs

**Files:**
- Modify: `src/figure_chain/schemas.py`
- Modify: `src/figure_chain/services/ai_jobs.py`
- Modify: `src/figure_chain/routers/ai_jobs.py`
- Test: `tests/figure_chain/test_ai_jobs_service.py`
- Test: `tests/figure_chain/test_ai_jobs_api.py`

- [ ] **Step 1: Write API service tests**

Add to `tests/figure_chain/test_ai_jobs_service.py`:

```python
def test_ai_jobs_service_cancels_job() -> None:
    repository = FakeJobRepository()
    service = AIJobsService(cast(Session, object()), repository=repository)

    response = service.cancel_job(JOB_ID, cancelled_by="lyl")

    assert response.id == JOB_ID
    assert repository.events[-1] == (JOB_ID, "cancel_requested")


def test_ai_jobs_service_retries_job_by_creating_new_job() -> None:
    repository = FakeJobRepository()
    service = AIJobsService(
        cast(Session, object()),
        repository=repository,
        get_candidate_detail_fn=lambda session, kind, candidate_id: cast(CandidateDetail, object()),
    )

    response = service.retry_job(JOB_ID, created_by="lyl")

    assert response.id == JOB_ID
    assert repository.created[-1].params["retry_of_job_id"] == str(JOB_ID)
```

- [ ] **Step 2: Write router tests**

Add to `tests/figure_chain/test_ai_jobs_api.py`:

```python
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
```

Extend `FakeAIJobsService` with `cancel_job()` and `retry_job()`.

- [ ] **Step 3: Run failing API tests**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_ai_jobs_service.py tests/figure_chain/test_ai_jobs_api.py -q
```

Expected: fail because schemas, service methods, and routes are missing.

- [ ] **Step 4: Add schemas**

In `src/figure_chain/schemas.py`, add:

```python
class AiJobCancelRequest(BaseModel):
    cancelled_by: str = Field(min_length=1)


class AiJobRetryRequest(BaseModel):
    created_by: str = Field(min_length=1)


class AiJobEventResponse(BaseModel):
    id: UUID
    job_id: UUID
    event_type: str
    actor: str
    message: str | None
    metadata: dict[str, object]
    created_at: datetime


class AiJobEventListResponse(BaseModel):
    items: list[AiJobEventResponse]
    count: int
```

- [ ] **Step 5: Add service methods**

Add to `AIJobsService`:

```python
    def cancel_job(self, job_id: UUID, *, cancelled_by: str) -> AiJobResponse:
        record = self._repository.get_job(self._session, job_id)
        if record is None:
            raise ApplicationError(
                code=ErrorCode.AI_JOB_NOT_FOUND,
                message="AI job was not found",
                details={"job_id": str(job_id)},
            )
        cancelled = self._repository.cancel_job(
            self._session,
            job_id,
            cancelled_by=cancelled_by,
        )
        self._repository.record_event(
            self._session,
            job_id=job_id,
            event_type="cancel_requested",
            actor=cancelled_by,
            metadata={"previous_status": record.status},
        )
        return self._job(cancelled)
```

Add `retry_job()` that loads the old job and calls existing `create_job()` with copied fields and `params={**old.params, "retry_of_job_id": str(old.id)}`.

- [ ] **Step 6: Add routes**

In `src/figure_chain/routers/ai_jobs.py`, add:

```python
@router.post("/{job_id}/cancel", response_model=AiJobResponse)
def cancel_ai_job(
    job_id: UUID,
    request: AiJobCancelRequest,
    service: Annotated[AIJobsService, Depends(get_ai_jobs_service)],
) -> AiJobResponse:
    return service.cancel_job(job_id, cancelled_by=request.cancelled_by)


@router.post("/{job_id}/retry", response_model=AiJobResponse)
def retry_ai_job(
    job_id: UUID,
    request: AiJobRetryRequest,
    service: Annotated[AIJobsService, Depends(get_ai_jobs_service)],
) -> AiJobResponse:
    return service.retry_job(job_id, created_by=request.created_by)
```

- [ ] **Step 7: Run API tests**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_ai_jobs_service.py tests/figure_chain/test_ai_jobs_api.py -q
```

Expected: pass.

- [ ] **Step 8: Commit Task 2**

```powershell
git add src/figure_chain/schemas.py src/figure_chain/services/ai_jobs.py src/figure_chain/routers/ai_jobs.py tests/figure_chain
git commit -m "feat: 增加 AI job 取消和重跑 API"
```

### Task 3: Add Retry Policy to Worker

**Files:**
- Modify: `src/figure_data/ai/job_runner.py`
- Test: `tests/ai/test_job_runner.py`

- [ ] **Step 1: Write retry tests**

Add to `tests/ai/test_job_runner.py`:

```python
def test_execute_ai_job_schedules_retry_for_provider_timeout() -> None:
    repository = FakeSingleJobRepository(_job())
    repository.scheduled_retries: list[tuple[UUID, str]] = []

    def schedule_retry(session: Session, job_id: UUID, **kwargs: object) -> AIGenerationJobRecord:
        repository.scheduled_retries.append((job_id, str(kwargs["error_code"])))
        return _job()

    repository.schedule_job_retry = schedule_retry  # type: ignore[method-assign]

    def generate(**kwargs: object) -> CandidateReviewSuggestionResult:
        raise RuntimeError("provider_timeout: request timed out")

    result = execute_ai_job(
        session=cast(Session, object()),
        settings=cast(Settings, object()),
        job_id=JOB_ID,
        worker_id="worker-1",
        repository=repository,
        generate_candidate_review_suggestion_fn=generate,
    )

    assert result.status == "retry_scheduled"
    assert repository.scheduled_retries == [(JOB_ID, "provider_timeout")]
```

- [ ] **Step 2: Run failing retry tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_runner.py -q
```

Expected: fail because retry scheduling is not integrated into `execute_ai_job()`.

- [ ] **Step 3: Add retry policy dataclass**

Add to `src/figure_data/ai/job_runner.py`:

```python
@dataclass(frozen=True)
class AIJobRetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: int = 10

    def delay_for_attempt(self, attempt_count: int) -> int:
        return self.base_delay_seconds * (2 ** max(attempt_count - 1, 0))
```

- [ ] **Step 4: Add retryable classification**

Add:

```python
RETRYABLE_ERROR_CODES = {
    "provider_timeout",
    "provider_rate_limited",
    "provider_unavailable",
}


def _is_retryable(error_code: str) -> bool:
    return error_code in RETRYABLE_ERROR_CODES
```

Update `_error_code()` to map timeout/rate limit/unavailable messages:

```python
    message = str(exc).lower()
    if "provider_timeout" in message or "timeout" in message:
        return "provider_timeout"
    if "provider_rate_limited" in message or "rate limit" in message:
        return "provider_rate_limited"
    if "provider_unavailable" in message:
        return "provider_unavailable"
```

- [ ] **Step 5: Schedule retry before final failure**

In `execute_ai_job()` exception branch, before `mark_failed()`:

```python
        if _is_retryable(error_code) and job.attempt_count < job.max_attempts:
            delay_seconds = AIJobRetryPolicy(
                max_attempts=job.max_attempts,
            ).delay_for_attempt(job.attempt_count)
            resolved_repository.schedule_job_retry(
                session,
                job.id,
                error_code=error_code,
                error_message=error_message,
                delay_seconds=delay_seconds,
            )
            resolved_repository.record_event(
                session,
                job_id=job.id,
                event_type="retry_scheduled",
                actor="worker",
                message=error_message,
                metadata={"delay_seconds": delay_seconds, "error_code": error_code},
            )
            return AIGenerationJobExecutionResult(
                job_id=job.id,
                status="retry_scheduled",
                error_code=error_code,
                error_message=error_message,
            )
```

- [ ] **Step 6: Run retry tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_runner.py -q
```

Expected: pass.

- [ ] **Step 7: Commit Task 3**

```powershell
git add src/figure_data/ai/job_runner.py tests/ai/test_job_runner.py
git commit -m "feat: 增加 AI job 自动重试策略"
```

### Task 4: Add Redis Rate Limiter

**Files:**
- Create: `src/figure_data/ai/job_rate_limit.py`
- Modify: `src/figure_data/ai/job_runner.py`
- Test: `tests/ai/test_job_rate_limit.py`
- Test: `tests/ai/test_job_runner.py`

- [ ] **Step 1: Write rate limiter tests**

Create `tests/ai/test_job_rate_limit.py`:

```python
from figure_data.ai.job_rate_limit import InMemoryRateLimiter


def test_in_memory_rate_limiter_allows_until_limit() -> None:
    limiter = InMemoryRateLimiter()

    assert limiter.allow("fake", "model", limit_per_minute=2)
    assert limiter.allow("fake", "model", limit_per_minute=2)
    assert not limiter.allow("fake", "model", limit_per_minute=2)
```

- [ ] **Step 2: Run failing rate limiter tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_rate_limit.py -q
```

Expected: fail because the module is missing.

- [ ] **Step 3: Implement rate limiter**

Create `src/figure_data/ai/job_rate_limit.py`:

```python
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Protocol


class AIJobRateLimiter(Protocol):
    def allow(self, provider: str, model_name: str, *, limit_per_minute: int) -> bool:
        """Return whether a provider/model call is allowed now."""


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._counts: dict[tuple[str, str, str], int] = defaultdict(int)

    def allow(self, provider: str, model_name: str, *, limit_per_minute: int) -> bool:
        minute = datetime.now(UTC).strftime("%Y%m%d%H%M")
        key = (provider, model_name, minute)
        self._counts[key] += 1
        return self._counts[key] <= limit_per_minute


class RedisRateLimiter:
    def __init__(self, redis_client: object) -> None:
        self._redis = redis_client

    def allow(self, provider: str, model_name: str, *, limit_per_minute: int) -> bool:
        minute = datetime.now(UTC).strftime("%Y%m%d%H%M")
        key = f"figurechain:ai:rate:{provider}:{model_name}:{minute}"
        value = int(self._redis.incr(key))
        if value == 1:
            self._redis.expire(key, 120)
        return value <= limit_per_minute
```

- [ ] **Step 4: Integrate optional limiter**

Update `execute_ai_job()` signature:

```python
    rate_limiter: AIJobRateLimiter | None = None,
```

Before `_run_job()`:

```python
        provider_name = getattr(settings, "ai_provider", None) or "unknown"
        model_name = getattr(settings, "ai_model", None) or "unknown"
        limit = int(getattr(settings, "ai_rate_limit_per_minute", 20))
        if rate_limiter is not None and not rate_limiter.allow(
            provider_name,
            model_name,
            limit_per_minute=limit,
        ):
            delay_seconds = AIJobRetryPolicy().delay_for_attempt(job.attempt_count)
            resolved_repository.schedule_job_retry(
                session,
                job.id,
                error_code="provider_rate_limited",
                error_message="provider rate limit reached",
                delay_seconds=delay_seconds,
            )
            resolved_repository.record_event(
                session,
                job_id=job.id,
                event_type="retry_scheduled",
                actor="worker",
                message="provider rate limit reached",
                metadata={"delay_seconds": delay_seconds},
            )
            return AIGenerationJobExecutionResult(
                job_id=job.id,
                status="retry_scheduled",
                error_code="provider_rate_limited",
                error_message="provider rate limit reached",
            )
```

- [ ] **Step 5: Run rate limit tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_rate_limit.py tests/ai/test_job_runner.py -q
```

Expected: pass.

- [ ] **Step 6: Commit Task 4**

```powershell
git add src/figure_data/ai/job_rate_limit.py src/figure_data/ai/job_runner.py tests/ai
git commit -m "feat: 增加 AI job Redis 限流"
```

### Task 5: Add Control CLI Commands

**Files:**
- Modify: `src/figure_data/cli.py`
- Test: `tests/ai/test_job_cli.py`

- [ ] **Step 1: Write CLI tests**

Add:

```python
def test_cancel_ai_job_help() -> None:
    result = runner.invoke(app, ["cancel-ai-job", "--help"])

    assert result.exit_code == 0
    assert "--job-id" in result.stdout
    assert "--cancelled-by" in result.stdout
```

- [ ] **Step 2: Run failing CLI tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_cli.py -q
```

Expected: fail because `cancel-ai-job` is missing.

- [ ] **Step 3: Implement CLI command**

Add to `src/figure_data/cli.py`:

```python
@app.command("cancel-ai-job")
def cancel_ai_job_command(
    job_id: Annotated[UUID, typer.Option("--job-id")],
    cancelled_by: Annotated[str, typer.Option("--cancelled-by")],
) -> None:
    """Request cancellation for an AI generation job."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with session_scope(factory) as session:
        job = get_job(session, job_id)
        if job is None:
            typer.echo(f"AI job not found: {job_id}", err=True)
            raise typer.Exit(code=1)
        if job.status == "queued":
            record = cancel_queued_job(session, job_id, cancelled_by=cancelled_by)
        elif job.status == "running":
            record = request_running_job_cancel(session, job_id, cancelled_by=cancelled_by)
        else:
            record = job
        record_job_event(
            session,
            job_id=job_id,
            event_type="cancel_requested",
            actor=cancelled_by,
            metadata={"previous_status": job.status, "new_status": record.status},
        )
    _echo_cli_line(f"ai_job_cancel\t{job_id}\tstatus={record.status}")
```

Add imports from `uuid` and `figure_data.ai.job_repository`.

- [ ] **Step 4: Run CLI tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_cli.py -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 5**

```powershell
git add src/figure_data/cli.py tests/ai/test_job_cli.py
git commit -m "feat: 增加 AI job 控制命令"
```

## Plan 3 Final Verification

- [ ] Run backend tests:

```powershell
uv run --no-sync pytest tests/ai tests/figure_chain tests/db -q
```

Expected: pass.

- [ ] Run quality checks:

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected: pass.
