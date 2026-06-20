# Admin Console AI Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `/admin/jobs` AI job 控制台，让本地维护者查看任务、事件、队列健康和 worker 状态，并执行 cancel、retry、requeue 操作。

**Architecture:** 后端新增 Admin AI Jobs service，复用现有 `AIJobsService`、`figure_data.ai.job_repository` 和 queue adapter，不复制模型调用逻辑。有副作用动作写入 `admin_operations`；requeue 从 CLI 入口层抽出为可复用服务，使 CLI 和 Admin API 共用同一实现。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Redis/RQ adapter, Pydantic v2, pytest, mypy, ruff, Next.js 16, React 19, TypeScript, Vitest。

---

## Preconditions

- Plan 1 已完成并提供 `admin_operations` repository 和 `/admin/operations`。
- 现有 AI job 能力可复用：
  - `src/figure_chain/services/ai_jobs.py`
  - `src/figure_chain/routers/ai_jobs.py`
  - `src/figure_data/ai/job_repository.py`
  - `src/figure_data/ai/queue.py`
  - `src/figure_data/ai/rq_worker.py`
- 当前计划不改变 job runner 的模型调用逻辑。
- 当前计划不新增 AI job 类型。

## Scope

本计划覆盖：

- Admin AI job list/detail/events/health API。
- Admin cancel/retry/requeue API。
- `requeue_ai_jobs` 共享服务，供 CLI 和 Admin API 使用。
- `/admin/jobs` 页面。
- Queue health、stale running、worker heartbeat 展示。
- CLI 预览和操作历史。

本计划不覆盖：

- 新 AI provider。
- 新 prompt。
- 新 job type。
- 分布式 worker 管理平台。
- 在浏览器中启动 worker 进程。

## Operation Types

Plan 4 使用以下 `admin_operations.operation_type`：

```text
cancel_ai_job
retry_ai_job
requeue_ai_jobs
```

`GET` 类查询不写入 `admin_operations`。

## File Structure

### Backend

- Modify: `src/figure_data/ai/job_repository.py`
  - Add admin list filters if Plan 2 resource queryer is not sufficient for `/admin/jobs`.
- Create: `src/figure_data/ai/requeue.py`
  - Shared requeue service extracted from CLI logic.
- Modify: `src/figure_data/cli.py`
  - Use `figure_data.ai.requeue.requeue_ai_jobs`.
- Create: `src/figure_chain/services/admin_ai_jobs.py`
  - Admin-facing AI job service with operation recording.
- Create: `src/figure_chain/routers/admin_ai_jobs.py`
  - Admin AI job endpoints.
- Modify: `src/figure_chain/dependencies.py`
  - Add `get_admin_ai_jobs_service`.
- Modify: `src/figure_chain/routers/__init__.py`
  - Include admin AI job router.
- Modify: `src/figure_chain/schemas.py`
  - Admin AI job request/response models.

### Tests

- Create: `tests/ai/test_requeue_service.py`
- Create: `tests/figure_chain/test_admin_ai_jobs_service.py`
- Create: `tests/figure_chain/test_admin_ai_jobs_api.py`
- Modify: `tests/ai/test_job_cli.py`
- Modify: `tests/figure_chain/test_app.py`

### Frontend

- Create: `frontend/app/admin/jobs/page.tsx`
- Create: `frontend/app/api/figure-chain/admin/ai/jobs/route.ts`
- Create: `frontend/app/api/figure-chain/admin/ai/jobs/[jobId]/route.ts`
- Create: `frontend/app/api/figure-chain/admin/ai/jobs/[jobId]/events/route.ts`
- Create: `frontend/app/api/figure-chain/admin/ai/jobs/[jobId]/cancel/route.ts`
- Create: `frontend/app/api/figure-chain/admin/ai/jobs/[jobId]/retry/route.ts`
- Create: `frontend/app/api/figure-chain/admin/ai/jobs/requeue/route.ts`
- Create: `frontend/app/api/figure-chain/admin/ai/health/route.ts`
- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/src/hooks/use-admin-ai-jobs.ts`
- Create: `frontend/src/components/admin-ai-jobs-page.tsx`
- Create: `frontend/tests/unit/admin-ai-jobs-api-routes.test.ts`
- Create: `frontend/tests/unit/admin-ai-jobs-page.test.tsx`

### Docs

- Modify: `README.md`

## Task 1: Extract Requeue Service

**Files:**
- Create: `src/figure_data/ai/requeue.py`
- Modify: `src/figure_data/cli.py`
- Create: `tests/ai/test_requeue_service.py`
- Modify: `tests/ai/test_job_cli.py`

- [ ] **Step 1: Write requeue service tests**

Create `tests/ai/test_requeue_service.py`:

```python
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from figure_data.ai.job_repository import AIGenerationJobRecord
from figure_data.ai.requeue import RequeueAIJobsResult, requeue_ai_jobs


@dataclass
class FakeQueue:
    enqueued: list[UUID] = field(default_factory=list)

    def enqueue(self, *, job_id: UUID, delay_seconds: int | None = None):
        self.enqueued.append(job_id)
        return type(
            "Enqueued",
            (),
            {
                "queue_backend": "rq",
                "queue_name": "figure-ai",
                "queue_job_id": f"rq-{job_id}",
            },
        )()


def _job(job_id: UUID) -> AIGenerationJobRecord:
    return AIGenerationJobRecord(
        id=job_id,
        job_type="candidate_review_suggestion",
        target_type="candidate",
        target_kind="relationship",
        target_id=1,
        status="queued",
        created_by="local",
        params={},
        result_ref_type=None,
        result_ref_id=None,
        error_code=None,
        error_message=None,
        started_at=None,
        finished_at=None,
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
        created_at=None,  # type: ignore[arg-type]
        updated_at=None,  # type: ignore[arg-type]
    )


def test_requeue_ai_jobs_enqueues_requeueable_jobs() -> None:
    job_id = uuid4()
    marked: list[UUID] = []
    events: list[UUID] = []

    result = requeue_ai_jobs(
        session=object(),  # type: ignore[arg-type]
        queue=FakeQueue(),
        actor="local",
        limit=10,
        list_requeueable_jobs_fn=lambda session, limit: [_job(job_id)],
        mark_enqueued_fn=lambda session, job_id, queue_backend, queue_name, queue_job_id: marked.append(job_id),
        record_event_fn=lambda session, job_id, event_type, actor, message, metadata: events.append(job_id),
    )

    assert result == RequeueAIJobsResult(scanned=1, enqueued=1, failed=0, job_ids=[job_id])
    assert marked == [job_id]
    assert events == [job_id]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_requeue_service.py -q
```

Expected: fail because `figure_data.ai.requeue` does not exist.

- [ ] **Step 3: Implement requeue service**

Create `src/figure_data/ai/requeue.py`:

- `RequeueAIJobsResult(scanned: int, enqueued: int, failed: int, job_ids: list[UUID])`.
- `requeue_ai_jobs(session, queue, actor, limit, ...) -> RequeueAIJobsResult`.
- Use `list_requeueable_jobs(session, limit=limit)`.
- For each job:
  - call `queue.enqueue(job_id=job.id)`;
  - call `mark_enqueued(...)`;
  - call `record_job_event(..., event_type="enqueued", actor=actor, message="AI job requeued", metadata={"queue_backend": ...})`.
- Catch per-job enqueue failures and continue; increment `failed`.
- Redact enqueue error messages before recording events.

- [ ] **Step 4: Update CLI**

Modify `requeue_ai_jobs_command` in `src/figure_data/cli.py` to call `requeue_ai_jobs(...)` instead of owning the loop. Preserve output fields:

```text
scanned
enqueued
failed
job_ids
```

- [ ] **Step 5: Run tests**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_requeue_service.py tests/ai/test_job_cli.py -q
```

Expected: tests pass.

- [ ] **Step 6: Commit requeue extraction**

Run:

```powershell
git add src/figure_data/ai/requeue.py src/figure_data/cli.py tests/ai/test_requeue_service.py tests/ai/test_job_cli.py
git commit -m "refactor: 复用 AI job requeue 服务"
```

## Task 2: Add Admin AI Jobs Service

**Files:**
- Modify: `src/figure_data/ai/job_repository.py`
- Create: `src/figure_chain/services/admin_ai_jobs.py`
- Modify: `src/figure_chain/schemas.py`
- Create: `tests/figure_chain/test_admin_ai_jobs_service.py`

- [ ] **Step 1: Write service tests**

Create `tests/figure_chain/test_admin_ai_jobs_service.py` with tests:

```python
def test_admin_ai_jobs_service_lists_jobs_with_status_filter() -> None: ...
def test_admin_ai_jobs_service_gets_job_events() -> None: ...
def test_admin_ai_jobs_service_records_cancel_operation() -> None: ...
def test_admin_ai_jobs_service_records_retry_operation() -> None: ...
def test_admin_ai_jobs_service_records_requeue_operation() -> None: ...
def test_admin_ai_jobs_service_returns_health() -> None: ...
```

Cancel/retry/requeue tests must assert an operation is created with operation types:

```text
cancel_ai_job
retry_ai_job
requeue_ai_jobs
```

- [ ] **Step 2: Run service tests and verify failure**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_ai_jobs_service.py -q
```

Expected: fail because `AdminAIJobsService` does not exist.

- [ ] **Step 3: Add admin job listing repository**

Add to `src/figure_data/ai/job_repository.py`:

- `AIJobListFilters(status: str | None, target_kind: str | None, target_id: int | None, queue_backend: str | None, limit: int, offset: int)`.
- `list_jobs(session, filters: AIJobListFilters) -> list[AIGenerationJobRecord]`.

The SQL must use explicit optional predicates:

```sql
where (:status is null or status = :status)
  and (:target_kind is null or target_kind = :target_kind)
  and (:target_id is null or target_id = :target_id)
  and (:queue_backend is null or queue_backend = :queue_backend)
order by created_at desc, id
limit :limit offset :offset
```

Clamp `limit` to 100 and `offset` to at least 0.

- [ ] **Step 4: Add schemas**

Append to `src/figure_chain/schemas.py`:

```python
class AdminAIJobListResponse(BaseModel):
    items: list[AiJobResponse]
    count: int
    limit: int
    offset: int


class AdminAIJobActionRequest(BaseModel):
    actor: str = Field(default="local", min_length=1, max_length=128)


class AdminAIJobsRequeueRequest(AdminAIJobActionRequest):
    limit: int = Field(default=50, ge=1, le=200)


class AdminAIJobActionResponse(BaseModel):
    operation_id: UUID
    operation_type: str
    status: str
    job: AiJobResponse | None = None
    result_summary: dict[str, object] = Field(default_factory=dict)
    preview: str
```

- [ ] **Step 5: Implement service**

Create `src/figure_chain/services/admin_ai_jobs.py`:

- Wrap existing `AIJobsService` for `get_job`, `list_job_events`, `cancel_job`, `retry_job`, and `get_queue_health`.
- Use new `list_jobs` repository for admin list without requiring target.
- On cancel:
  - create admin operation with payload `{job_id, actor}`;
  - call `AIJobsService.cancel_job(job_id, cancelled_by=actor)`;
  - mark operation succeeded with `result_summary={"job_id": str(job_id), "status": job.status}`.
- On retry:
  - create admin operation with payload `{job_id, actor}`;
  - call `AIJobsService.retry_job(job_id, created_by=actor)`;
  - mark operation succeeded.
- On requeue:
  - create admin operation with payload `{actor, limit}`;
  - call `requeue_ai_jobs(session, queue, actor=actor, limit=limit)`;
  - mark operation succeeded with scanned/enqueued/failed/job_ids.
- On failure:
  - mark operation failed with redacted error and raise the original `ApplicationError` or wrap unknown errors as `ApplicationError(ErrorCode.INTERNAL_ERROR, "admin AI job action failed")`.

- [ ] **Step 6: Run service tests**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_ai_jobs_service.py -q
```

Expected: tests pass.

- [ ] **Step 7: Commit service**

Run:

```powershell
git add src/figure_data/ai/job_repository.py src/figure_chain/services/admin_ai_jobs.py src/figure_chain/schemas.py tests/figure_chain/test_admin_ai_jobs_service.py
git commit -m "feat: 添加后台 AI job 服务"
```

## Task 3: Add Admin AI Jobs API

**Files:**
- Create: `src/figure_chain/routers/admin_ai_jobs.py`
- Modify: `src/figure_chain/dependencies.py`
- Modify: `src/figure_chain/routers/__init__.py`
- Create: `tests/figure_chain/test_admin_ai_jobs_api.py`
- Modify: `tests/figure_chain/test_app.py`

- [ ] **Step 1: Write API tests**

Create tests for:

```python
def test_admin_ai_jobs_api_requires_operator_role() -> None: ...
def test_admin_ai_jobs_api_lists_jobs() -> None: ...
def test_admin_ai_jobs_api_gets_job_detail() -> None: ...
def test_admin_ai_jobs_api_lists_events() -> None: ...
def test_admin_ai_jobs_api_cancels_job() -> None: ...
def test_admin_ai_jobs_api_retries_job() -> None: ...
def test_admin_ai_jobs_api_requeues_jobs() -> None: ...
def test_admin_ai_jobs_api_gets_health() -> None: ...
```

- [ ] **Step 2: Run API tests and verify failure**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_ai_jobs_api.py -q
```

Expected: fail because admin AI jobs router does not exist.

- [ ] **Step 3: Add dependency**

Add `get_admin_ai_jobs_service` to `src/figure_chain/dependencies.py`. It should build:

- `AIJobsService(pg_session, queue=create_ai_job_queue(settings), queue_name=settings.ai_queue_name, job_timeout_seconds=settings.ai_job_timeout_seconds)`.
- `AdminAIJobsService(pg_session, ai_jobs_service=..., queue=...)`.

- [ ] **Step 4: Implement router**

Create `src/figure_chain/routers/admin_ai_jobs.py` with prefix `/api/v1/admin/ai`.

Routes:

```text
GET  /health
GET  /jobs
POST /jobs/requeue
GET  /jobs/{job_id}
GET  /jobs/{job_id}/events
POST /jobs/{job_id}/cancel
POST /jobs/{job_id}/retry
```

Define `/jobs/requeue` before `/jobs/{job_id}` in the file so FastAPI does not treat `requeue` as a UUID path parameter.

All endpoints require `require_operator_context`.

- [ ] **Step 5: Register router and update app tests**

Update `src/figure_chain/routers/__init__.py` to include `admin_ai_jobs.router`.

Update `tests/figure_chain/test_app.py`:

```python
assert "/api/v1/admin/ai/health" in route_paths
assert "/api/v1/admin/ai/jobs" in route_paths
assert "/api/v1/admin/ai/jobs/requeue" in route_paths
assert "/api/v1/admin/ai/jobs/{job_id}" in route_paths
assert "/api/v1/admin/ai/jobs/{job_id}/events" in route_paths
assert "/api/v1/admin/ai/jobs/{job_id}/cancel" in route_paths
assert "/api/v1/admin/ai/jobs/{job_id}/retry" in route_paths
```

- [ ] **Step 6: Run API tests**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_ai_jobs_api.py tests/figure_chain/test_app.py -q
```

Expected: tests pass.

- [ ] **Step 7: Commit API**

Run:

```powershell
git add src/figure_chain/routers/admin_ai_jobs.py src/figure_chain/dependencies.py src/figure_chain/routers/__init__.py tests/figure_chain/test_admin_ai_jobs_api.py tests/figure_chain/test_app.py
git commit -m "feat: 添加后台 AI job API"
```

## Task 4: Add Frontend AI Jobs Proxy And Hook

**Files:**
- Create: `frontend/app/api/figure-chain/admin/ai/jobs/route.ts`
- Create: `frontend/app/api/figure-chain/admin/ai/jobs/[jobId]/route.ts`
- Create: `frontend/app/api/figure-chain/admin/ai/jobs/[jobId]/events/route.ts`
- Create: `frontend/app/api/figure-chain/admin/ai/jobs/[jobId]/cancel/route.ts`
- Create: `frontend/app/api/figure-chain/admin/ai/jobs/[jobId]/retry/route.ts`
- Create: `frontend/app/api/figure-chain/admin/ai/jobs/requeue/route.ts`
- Create: `frontend/app/api/figure-chain/admin/ai/health/route.ts`
- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/src/hooks/use-admin-ai-jobs.ts`
- Create: `frontend/tests/unit/admin-ai-jobs-api-routes.test.ts`

- [ ] **Step 1: Write route tests**

Create `frontend/tests/unit/admin-ai-jobs-api-routes.test.ts` asserting:

- Query keys forwarded for list: `status`, `target_kind`, `target_id`, `queue_backend`, `limit`, `offset`.
- Dynamic `jobId` is forwarded to detail/events/cancel/retry.
- POST bodies are forwarded unchanged.
- Operator headers are present.

- [ ] **Step 2: Implement route handlers**

Use `buildForwardPath` for list and health query parameters. POST handlers use:

```ts
return forwardToFigureChain(`/api/v1/admin/ai/jobs/${params.jobId}/cancel`, {
  method: "POST",
  headers: ADMIN_HEADERS,
  body: await request.text(),
});
```

- [ ] **Step 3: Add TypeScript types**

Append:

```ts
export type AdminAIJobListResponse = {
  items: AiJobResponse[];
  count: number;
  limit: number;
  offset: number;
};

export type AdminAIJobActionResponse = {
  operation_id: string;
  operation_type: string;
  status: string;
  job: AiJobResponse | null;
  result_summary: Record<string, unknown>;
  preview: string;
};
```

- [ ] **Step 4: Add hook**

Create `frontend/src/hooks/use-admin-ai-jobs.ts`:

- `useAdminAIJobs(filters)`
- `useAdminAIJob(jobId)`
- `useAdminAIJobEvents(jobId)`
- `useAdminAIJobHealth()`
- `useAdminAIJobActions()`

Actions:

- `cancelJob(jobId, actor)`
- `retryJob(jobId, actor)`
- `requeueJobs(actor, limit)`

- [ ] **Step 5: Run frontend tests**

Run:

```powershell
npm --prefix frontend test -- admin-ai-jobs-api-routes
npm --prefix frontend run typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 6: Commit proxy and hook**

Run:

```powershell
git add frontend/app/api/figure-chain/admin/ai frontend/src/lib/figure-chain-types.ts frontend/src/hooks/use-admin-ai-jobs.ts frontend/tests/unit/admin-ai-jobs-api-routes.test.ts
git commit -m "feat: 添加后台 AI job 前端代理"
```

## Task 5: Add Admin AI Jobs Page

**Files:**
- Create: `frontend/app/admin/jobs/page.tsx`
- Create: `frontend/src/components/admin-ai-jobs-page.tsx`
- Create: `frontend/tests/unit/admin-ai-jobs-page.test.tsx`

- [ ] **Step 1: Write page tests**

Create tests asserting:

- Health counters render.
- Job status/target filters render.
- Job table renders id, target, status, queue backend, attempts, worker id, heartbeat.
- Selecting a job renders events.
- Cancel and retry buttons render for valid statuses.
- Requeue button shows returned operation id and CLI preview.

- [ ] **Step 2: Implement page component**

Create `frontend/src/components/admin-ai-jobs-page.tsx`:

- Dense workbench layout.
- Top health strip:
  - queued
  - running
  - stale running
  - failed
  - cancelled
- Filter row:
  - status select
  - target kind select
  - target id input
  - queue backend select
  - limit select
- Main table with fixed columns and horizontal scroll.
- Side detail panel for selected job events.
- Action panel:
  - cancel selected job
  - retry selected job
  - requeue recoverable jobs
- Show CLI previews:
  - `figure-data cancel-ai-job --job-id <id> --cancelled-by <actor>`
  - `figure-data retry-ai-job --job-id <id> --created-by <actor>`
  - `figure-data requeue-ai-jobs --limit <limit>`

- [ ] **Step 3: Create page route**

Create `frontend/app/admin/jobs/page.tsx`:

```tsx
import { AdminAIJobsPage } from "@/components/admin-ai-jobs-page";

export default function AdminJobsPage() {
  return <AdminAIJobsPage />;
}
```

- [ ] **Step 4: Run frontend tests**

Run:

```powershell
npm --prefix frontend test -- admin-ai-jobs-page
npm --prefix frontend run typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 5: Commit page**

Run:

```powershell
git add frontend/app/admin/jobs/page.tsx frontend/src/components/admin-ai-jobs-page.tsx frontend/tests/unit/admin-ai-jobs-page.test.tsx
git commit -m "feat: 添加后台 AI job 页面"
```

## Task 6: Document And Verify Plan 4

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add:

```md
### AI job 控制台

AI job 控制台入口：

```text
http://127.0.0.1:3000/admin/jobs
```

该页面可以查看 AI job、事件、队列健康和 worker heartbeat，并执行 cancel、retry 和 requeue。浏览器不会直接连接 Redis/RQ；所有动作通过 FastAPI service 执行并记录到 `admin_operations`。
```

- [ ] **Step 2: Run focused verification**

Run:

```powershell
uv run --no-sync pytest tests/ai/test_requeue_service.py tests/ai/test_job_cli.py tests/figure_chain/test_admin_ai_jobs_service.py tests/figure_chain/test_admin_ai_jobs_api.py tests/figure_chain/test_app.py -q
npm --prefix frontend test -- admin-ai-jobs
npm --prefix frontend run typecheck
```

Expected:

- Backend focused tests pass.
- Frontend AI job tests pass.
- Frontend typecheck passes.

- [ ] **Step 3: Run static checks**

Run:

```powershell
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
```

Expected:

- Ruff passes.
- Mypy passes.

- [ ] **Step 4: Commit docs**

Run:

```powershell
git add README.md
git commit -m "docs: 记录后台 AI job 控制台"
```

## Final Acceptance

Plan 4 is complete when:

- `/api/v1/admin/ai/jobs` lists jobs without requiring a specific target.
- `/api/v1/admin/ai/jobs/{job_id}` returns job detail.
- `/api/v1/admin/ai/jobs/{job_id}/events` returns events.
- `/api/v1/admin/ai/health` returns queue health.
- Cancel, retry, and requeue actions write `admin_operations`.
- Requeue logic is shared between CLI and Admin API.
- `/admin/jobs` renders health, filters, job table, event detail, actions, operation links, and CLI previews.
- Verification commands in Task 6 pass.

## Follow-Up

Plan 5 should migrate the existing review workspace into `/admin/review` and record review actions in `admin_operations`.
