# Redis/RQ AI Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make RQ the primary execution path for persisted AI jobs while preserving the existing database polling runner as fallback.

**Architecture:** Introduce a single-job execution function that is safe to call from RQ. The worker opens its own PostgreSQL session, atomically claims the specific job by id, executes the existing job dispatch logic, and writes the result or failure back to PostgreSQL.

**Tech Stack:** Python 3.12, RQ, Redis, SQLAlchemy, Typer, PostgreSQL, pytest, ruff, mypy.

---

## References

- Foundation plan: `docs/superpowers/plans/2026-06-19-redis-rq-ai-jobs-foundation.md`
- Spec: `docs/superpowers/specs/2026-06-19-redis-rq-ai-jobs-priority-design.md`
- Existing runner: `src/figure_data/ai/job_runner.py`
- Existing CLI: `src/figure_data/cli.py`

## Prerequisites

Complete and verify `2026-06-19-redis-rq-ai-jobs-foundation.md` before starting this plan. This plan expects queue metadata fields, `ai_job_events`, and `src/figure_data/ai/queue.py` to exist.

## File Structure

- Modify `src/figure_data/ai/job_repository.py`: add specific job claim and heartbeat functions.
- Modify `src/figure_data/ai/job_runner.py`: add single-job executor while preserving `run_ai_jobs`.
- Create `src/figure_data/ai/rq_worker.py`: RQ task function and worker factory helper.
- Modify `src/figure_data/cli.py`: add `run-ai-worker`.
- Modify `src/figure_data/ai/queue.py`: confirm worker target points to the new task.
- Test `tests/ai/test_job_repository.py`: specific claim and heartbeat.
- Test `tests/ai/test_job_runner.py`: single-job executor success/failure/skip behavior.
- Create `tests/ai/test_rq_worker.py`: task function wiring.
- Modify `tests/ai/test_job_cli.py`: CLI help and argument validation.

### Task 1: Add Specific Job Claim and Heartbeat Repository Functions

**Files:**
- Modify: `src/figure_data/ai/job_repository.py`
- Test: `tests/ai/test_job_repository.py`

- [ ] **Step 1: Write failing repository tests**

Add to `tests/ai/test_job_repository.py`:

```python
def test_claim_queued_job_by_id_marks_worker_metadata() -> None:
    session = FakeSession()

    record = claim_queued_job_by_id(
        session,  # type: ignore[arg-type]
        JOB_ID,
        worker_id="worker-1",
    )

    assert record is not None
    assert record.status == "running"
    statement = session.statements[0].lower()
    assert "where id = :job_id" in statement
    assert "status = :queued_status" in statement
    assert session.params[0]["worker_id"] == "worker-1"


def test_touch_job_heartbeat_updates_worker_timestamp() -> None:
    session = FakeSession()

    touch_job_heartbeat(
        session,  # type: ignore[arg-type]
        JOB_ID,
        worker_id="worker-1",
    )

    assert "heartbeat_at = :now" in session.statements[0]
    assert session.params[0]["worker_id"] == "worker-1"
```

- [ ] **Step 2: Run failing repository tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_repository.py -q
```

Expected: fail because `claim_queued_job_by_id` and `touch_job_heartbeat` are missing.

- [ ] **Step 3: Implement claim by id**

Add to `src/figure_data/ai/job_repository.py`:

```python
def claim_queued_job_by_id(
    session: Session,
    job_id: UUID,
    *,
    worker_id: str,
) -> AIGenerationJobRecord | None:
    row = (
        session.execute(
            text(
                f"""
                update figure_data.ai_generation_jobs
                set status = :running_status,
                    started_at = coalesce(started_at, :now),
                    worker_id = :worker_id,
                    heartbeat_at = :now,
                    attempt_count = attempt_count + 1,
                    updated_at = :now
                where id = :job_id
                  and status = :queued_status
                  and (next_run_at is null or next_run_at <= :now)
                  and cancel_requested_at is null
                returning {_select_columns()}
                """
            ),
            {
                "job_id": job_id,
                "queued_status": AIJobStatus.QUEUED.value,
                "running_status": AIJobStatus.RUNNING.value,
                "worker_id": worker_id,
                "now": datetime.now(UTC),
            },
        )
        .mappings()
        .one_or_none()
    )
    return _record_from_row(cast(Mapping[str, Any], row)) if row is not None else None
```

- [ ] **Step 4: Implement heartbeat**

Add:

```python
def touch_job_heartbeat(
    session: Session,
    job_id: UUID,
    *,
    worker_id: str,
) -> None:
    session.execute(
        text(
            """
            update figure_data.ai_generation_jobs
            set worker_id = :worker_id,
                heartbeat_at = :now,
                updated_at = :now
            where id = :job_id
              and status = :running_status
            """
        ),
        {
            "job_id": job_id,
            "worker_id": worker_id,
            "running_status": AIJobStatus.RUNNING.value,
            "now": datetime.now(UTC),
        },
    )
```

- [ ] **Step 5: Run repository tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_repository.py -q
```

Expected: pass.

- [ ] **Step 6: Commit Task 1**

```powershell
git add src/figure_data/ai/job_repository.py tests/ai/test_job_repository.py
git commit -m "feat: 增加 AI job 定向领取"
```

### Task 2: Add Single Job Executor

**Files:**
- Modify: `src/figure_data/ai/job_runner.py`
- Test: `tests/ai/test_job_runner.py`

- [ ] **Step 1: Write executor tests**

Add to `tests/ai/test_job_runner.py`:

```python
class FakeSingleJobRepository(FakeJobRepository):
    def __init__(self, job: AIGenerationJobRecord | None) -> None:
        super().__init__([job] if job is not None else [])
        self.claimed_job_id: UUID | None = None
        self.worker_id: str | None = None
        self.events: list[str] = []

    def claim_queued_job_by_id(
        self,
        session: Session,
        job_id: UUID,
        *,
        worker_id: str,
    ) -> AIGenerationJobRecord | None:
        self.claimed_job_id = job_id
        self.worker_id = worker_id
        return self.jobs[0] if self.jobs else None

    def record_event(
        self,
        session: Session,
        *,
        job_id: UUID,
        event_type: str,
        actor: str,
        message: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> UUID:
        self.events.append(event_type)
        return job_id


def test_execute_ai_job_claims_specific_job_and_marks_success() -> None:
    repository = FakeSingleJobRepository(_job())

    def generate(**kwargs: object) -> CandidateReviewSuggestionResult:
        return CandidateReviewSuggestionResult(
            ai_run_id=AI_RUN_ID,
            suggestion=_suggestion(),
        )

    result = execute_ai_job(
        session=cast(Session, object()),
        settings=cast(Settings, object()),
        job_id=JOB_ID,
        worker_id="worker-1",
        repository=repository,
        generate_candidate_review_suggestion_fn=generate,
    )

    assert result.status == "succeeded"
    assert repository.claimed_job_id == JOB_ID
    assert repository.worker_id == "worker-1"
    assert repository.succeeded == [(JOB_ID, "ai_candidate_review_suggestion", SUGGESTION_ID)]
    assert "started" in repository.events
    assert "succeeded" in repository.events


def test_execute_ai_job_skips_when_claim_returns_none() -> None:
    repository = FakeSingleJobRepository(None)

    result = execute_ai_job(
        session=cast(Session, object()),
        settings=cast(Settings, object()),
        job_id=JOB_ID,
        worker_id="worker-1",
        repository=repository,
    )

    assert result.status == "skipped"
    assert repository.succeeded == []
    assert repository.failed == []
```

- [ ] **Step 2: Run failing executor tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_runner.py -q
```

Expected: fail because `execute_ai_job` does not exist.

- [ ] **Step 3: Extend repository protocol**

Update `AIGenerationJobRepository` in `src/figure_data/ai/job_runner.py`:

```python
    def claim_queued_job_by_id(
        self,
        session: Session,
        job_id: UUID,
        *,
        worker_id: str,
    ) -> AIGenerationJobRecord | None:
        """Claim a single queued job by id."""

    def record_event(
        self,
        session: Session,
        *,
        job_id: UUID,
        event_type: str,
        actor: str,
        message: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> UUID:
        """Record a job event."""
```

Implement these in `PostgresAIGenerationJobRepository`.

- [ ] **Step 4: Add executor result dataclass**

Add:

```python
@dataclass(frozen=True)
class AIGenerationJobExecutionResult:
    job_id: UUID
    status: str
    error_code: str | None = None
    error_message: str | None = None
```

- [ ] **Step 5: Implement `execute_ai_job`**

Add:

```python
def execute_ai_job(
    *,
    session: Session,
    settings: Settings,
    job_id: UUID,
    worker_id: str,
    repository: AIGenerationJobRepository | None = None,
    generate_candidate_review_suggestion_fn: GenerateCandidateReviewSuggestionFn = (
        generate_candidate_review_suggestion
    ),
) -> AIGenerationJobExecutionResult:
    resolved_repository = repository or PostgresAIGenerationJobRepository()
    job = resolved_repository.claim_queued_job_by_id(
        session,
        job_id,
        worker_id=worker_id,
    )
    if job is None:
        return AIGenerationJobExecutionResult(job_id=job_id, status="skipped")

    resolved_repository.record_event(
        session,
        job_id=job.id,
        event_type="started",
        actor="worker",
        metadata={"worker_id": worker_id},
    )
    try:
        result = _run_job(
            session=session,
            settings=settings,
            job=job,
            generate_candidate_review_suggestion_fn=generate_candidate_review_suggestion_fn,
        )
        resolved_repository.mark_succeeded(
            session,
            job.id,
            result_ref_type="ai_candidate_review_suggestion",
            result_ref_id=result.suggestion.id,
        )
        resolved_repository.record_event(
            session,
            job_id=job.id,
            event_type="succeeded",
            actor="worker",
            metadata={"result_ref_id": str(result.suggestion.id)},
        )
        return AIGenerationJobExecutionResult(job_id=job.id, status="succeeded")
    except Exception as exc:
        error_code = _error_code(exc)
        error_message = _error_message(exc)
        resolved_repository.mark_failed(
            session,
            job.id,
            error_code=error_code,
            error_message=error_message,
        )
        resolved_repository.record_event(
            session,
            job_id=job.id,
            event_type="failed",
            actor="worker",
            message=error_message,
            metadata={"error_code": error_code},
        )
        return AIGenerationJobExecutionResult(
            job_id=job.id,
            status="failed",
            error_code=error_code,
            error_message=error_message,
        )
```

- [ ] **Step 6: Keep DB fallback behavior**

Update `run_ai_jobs()` to keep using `claim_queued_jobs()` and existing summary output. Do not route DB fallback through RQ.

- [ ] **Step 7: Run runner tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_runner.py -q
```

Expected: pass.

- [ ] **Step 8: Commit Task 2**

```powershell
git add src/figure_data/ai/job_runner.py tests/ai/test_job_runner.py
git commit -m "feat: 增加 AI job 单任务执行器"
```

### Task 3: Add RQ Task Function

**Files:**
- Create: `src/figure_data/ai/rq_worker.py`
- Test: `tests/ai/test_rq_worker.py`

- [ ] **Step 1: Write RQ task tests**

Create `tests/ai/test_rq_worker.py`:

```python
from uuid import UUID

from figure_data.ai.rq_worker import execute_ai_job_task

JOB_ID = UUID("00000000-0000-0000-0000-000000000501")


def test_execute_ai_job_task_passes_job_id_to_executor(monkeypatch) -> None:
    calls: list[UUID] = []

    def fake_run(job_id: UUID) -> str:
        calls.append(job_id)
        return "succeeded"

    monkeypatch.setattr("figure_data.ai.rq_worker._execute_with_new_session", fake_run)

    result = execute_ai_job_task(str(JOB_ID))

    assert result == "succeeded"
    assert calls == [JOB_ID]
```

- [ ] **Step 2: Run failing RQ task tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_rq_worker.py -q
```

Expected: fail because `rq_worker.py` does not exist.

- [ ] **Step 3: Implement RQ task module**

Create `src/figure_data/ai/rq_worker.py`:

```python
from __future__ import annotations

import socket
from uuid import UUID

from figure_data.ai.job_runner import execute_ai_job
from figure_data.config import load_settings
from figure_data.db.session import create_session_factory


def execute_ai_job_task(job_id: str) -> str:
    """RQ entrypoint for executing one persisted AI job."""
    return _execute_with_new_session(UUID(job_id))


def _execute_with_new_session(job_id: UUID) -> str:
    settings = load_settings()
    factory = create_session_factory(settings)
    worker_id = socket.gethostname()
    with factory() as session:
        try:
            result = execute_ai_job(
                session=session,
                settings=settings,
                job_id=job_id,
                worker_id=worker_id,
            )
            session.commit()
            return result.status
        except Exception:
            session.rollback()
            raise
```

- [ ] **Step 4: Run RQ task tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_rq_worker.py -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add src/figure_data/ai/rq_worker.py tests/ai/test_rq_worker.py
git commit -m "feat: 增加 RQ AI job 任务入口"
```

### Task 4: Add `run-ai-worker` CLI

**Files:**
- Modify: `src/figure_data/cli.py`
- Test: `tests/ai/test_job_cli.py`

- [ ] **Step 1: Write CLI tests**

Add to `tests/ai/test_job_cli.py`:

```python
def test_run_ai_worker_help() -> None:
    result = runner.invoke(app, ["run-ai-worker", "--help"])

    assert result.exit_code == 0
    assert "--queue" in result.stdout


def test_run_ai_worker_requires_rq_backend(monkeypatch) -> None:
    settings = type(
        "Settings",
        (),
        {
            "ai_queue_backend": "database",
            "redis_url": None,
            "ai_queue_name": "figure-ai",
        },
    )()
    monkeypatch.setattr("figure_data.cli.load_settings", lambda: settings)

    result = runner.invoke(app, ["run-ai-worker"])

    assert result.exit_code == 1
    assert "FIGURE_AI_QUEUE_BACKEND must be 'rq'" in result.stderr
```

- [ ] **Step 2: Run failing CLI tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_cli.py -q
```

Expected: fail because the command is missing.

- [ ] **Step 3: Implement CLI command**

Add imports to `src/figure_data/cli.py`:

```python
from redis import Redis
from rq import Queue, Worker
```

Add command:

```python
@app.command("run-ai-worker")
def run_ai_worker_command(
    queue_name: Annotated[str | None, typer.Option("--queue")] = None,
) -> None:
    """Run an RQ worker for AI generation jobs."""
    settings = load_settings()
    if settings.ai_queue_backend != "rq":
        typer.echo("FIGURE_AI_QUEUE_BACKEND must be 'rq' to run RQ worker", err=True)
        raise typer.Exit(code=1)
    if settings.redis_url is None:
        typer.echo("REDIS_URL is required to run RQ worker", err=True)
        raise typer.Exit(code=1)

    resolved_queue_name = queue_name or settings.ai_queue_name
    redis_connection = Redis.from_url(settings.redis_url)
    queue = Queue(name=resolved_queue_name, connection=redis_connection)
    worker = Worker([queue], connection=redis_connection)
    worker.work()
```

- [ ] **Step 4: Run CLI tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_job_cli.py -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 4**

```powershell
git add src/figure_data/cli.py tests/ai/test_job_cli.py
git commit -m "feat: 增加 RQ AI worker 命令"
```

## Plan 2 Final Verification

- [ ] Run focused tests:

```powershell
uv run --no-sync pytest tests/ai/test_job_repository.py tests/ai/test_job_runner.py tests/ai/test_rq_worker.py tests/ai/test_job_cli.py -q
```

Expected: pass.

- [ ] Run broader backend tests:

```powershell
uv run --no-sync pytest tests/ai tests/figure_chain -q
```

Expected: pass.

- [ ] Run quality checks:

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected: pass.


