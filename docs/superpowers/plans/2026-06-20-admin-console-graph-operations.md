# Admin Console Graph Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `/admin/graph` 图同步控制台，让本地维护者查看 Neo4j 投影状态，并通过 `admin_operations` 触发和轮询 validate/sync 操作。

**Architecture:** 后端新增本地后台 operation runner，把有副作用或耗时的图操作记录到 `figure_data.admin_operations`，再用 FastAPI `BackgroundTasks` 调用既有 graph service 函数。PostgreSQL 继续作为事实源，Neo4j 只通过 `figure_data.graph.projection` 和 `figure_data.graph.validation` 更新或校验。

**Tech Stack:** Python 3.12, FastAPI BackgroundTasks, SQLAlchemy, Neo4j driver, Pydantic v2, pytest, mypy, ruff, Next.js 16, React 19, TypeScript, Vitest。

---

## Preconditions

- Plan 1 已完成并提供：
  - `figure_data.admin_operations`。
  - `figure_data.admin.operations` repository。
  - `GET /api/v1/admin/operations/{operation_id}`。
  - `/admin/operations` 页面。
- 本计划复用现有函数：
  - `figure_data.encounters.validation.validate_encounters`
  - `figure_data.graph.projection.sync_graph_rebuild`
  - `figure_data.graph.projection.sync_graph_incremental`
  - `figure_data.graph.validation.validate_graph`
  - `figure_data.graph.batches.get_latest_projection_batch`
- 本计划不调用 `figure-data` shell 命令。

## Scope

本计划覆盖：

- 本地后台 operation runner。
- Graph status API。
- Graph validate/sync/validate-graph API。
- `/admin/graph` 页面。
- stale running operation 标识。
- CLI 预览。

本计划不覆盖：

- 把后台 operation 迁移到 RQ。
- 自动定时同步 Neo4j。
- 资源查询器。
- AI job 控制台。

## Operation Types

Plan 3 使用以下 `admin_operations.operation_type`：

```text
validate_encounters
sync_graph_rebuild
sync_graph_incremental
validate_graph
```

Status transition:

```text
queued -> running -> succeeded
queued -> running -> failed
```

如果 FastAPI 进程退出导致 operation 长期停留 `running`，status API 返回 `stale_running_operations`，不自动改写历史状态。

## File Structure

### Backend

- Create: `src/figure_data/admin/operation_runner.py`
  - 本地后台 operation runner，负责 status transition 和异常记录。
- Create: `src/figure_chain/services/admin_graph.py`
  - Graph status and action orchestration.
- Create: `src/figure_chain/routers/admin_graph.py`
  - Admin graph endpoints.
- Modify: `src/figure_chain/dependencies.py`
  - Add `get_admin_graph_service`.
- Modify: `src/figure_chain/routers/__init__.py`
  - Include graph router.
- Modify: `src/figure_chain/schemas.py`
  - Graph admin request/response models.

### Tests

- Create: `tests/admin/test_operation_runner.py`
- Create: `tests/figure_chain/test_admin_graph_service.py`
- Create: `tests/figure_chain/test_admin_graph_api.py`
- Modify: `tests/figure_chain/test_app.py`

### Frontend

- Create: `frontend/app/admin/graph/page.tsx`
- Create: `frontend/app/api/figure-chain/admin/graph/status/route.ts`
- Create: `frontend/app/api/figure-chain/admin/graph/validate-encounters/route.ts`
- Create: `frontend/app/api/figure-chain/admin/graph/sync/route.ts`
- Create: `frontend/app/api/figure-chain/admin/graph/validate-graph/route.ts`
- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/src/hooks/use-admin-graph.ts`
- Create: `frontend/src/components/admin-graph-page.tsx`
- Create: `frontend/tests/unit/admin-graph-api-routes.test.ts`
- Create: `frontend/tests/unit/admin-graph-page.test.tsx`

### Docs

- Modify: `README.md`

## Task 1: Add Local Admin Operation Runner

**Files:**
- Create: `src/figure_data/admin/operation_runner.py`
- Create: `tests/admin/test_operation_runner.py`

- [ ] **Step 1: Write runner tests**

Create `tests/admin/test_operation_runner.py`:

```python
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from figure_data.admin.operation_runner import run_admin_operation


@dataclass
class FakeSession:
    committed: int = 0
    rolled_back: int = 0

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        self.rolled_back += 1


@dataclass
class FakeFactory:
    session: FakeSession = field(default_factory=FakeSession)

    def __call__(self) -> FakeSession:
        return self.session


def test_run_admin_operation_marks_success() -> None:
    operation_id = uuid4()
    events: list[tuple[str, UUID, dict[str, object] | None]] = []

    def mark_running(session: object, op_id: UUID) -> None:
        events.append(("running", op_id, None))

    def mark_finished(
        session: object,
        op_id: UUID,
        *,
        status: str,
        result_summary: dict[str, object] | None = None,
        error_message: str | None = None,
    ) -> None:
        events.append((status, op_id, result_summary))

    def action(session: object) -> dict[str, object]:
        return {"checks": 8, "failed": 0}

    factory = FakeFactory()
    run_admin_operation(
        session_factory=factory,  # type: ignore[arg-type]
        operation_id=operation_id,
        action=action,
        mark_running_fn=mark_running,
        mark_finished_fn=mark_finished,
    )

    assert events == [
        ("running", operation_id, None),
        ("succeeded", operation_id, {"checks": 8, "failed": 0}),
    ]
    assert factory.session.committed == 2


def test_run_admin_operation_marks_failure_with_redacted_message() -> None:
    operation_id = uuid4()
    statuses: list[str] = []
    errors: list[str | None] = []

    def mark_running(session: object, op_id: UUID) -> None:
        statuses.append("running")

    def mark_finished(
        session: object,
        op_id: UUID,
        *,
        status: str,
        result_summary: dict[str, object] | None = None,
        error_message: str | None = None,
    ) -> None:
        statuses.append(status)
        errors.append(error_message)

    def action(session: object) -> dict[str, object]:
        raise RuntimeError("provider token=secret-value failed")

    run_admin_operation(
        session_factory=FakeFactory(),  # type: ignore[arg-type]
        operation_id=operation_id,
        action=action,
        mark_running_fn=mark_running,
        mark_finished_fn=mark_finished,
    )

    assert statuses == ["running", "failed"]
    assert errors == ["provider token=[REDACTED] failed"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv run --no-sync pytest tests/admin/test_operation_runner.py -q
```

Expected: fail because `figure_data.admin.operation_runner` does not exist.

- [ ] **Step 3: Implement runner**

Create `src/figure_data/admin/operation_runner.py`:

- Accept a `session_factory`, `operation_id`, and `action(session) -> dict[str, object]`.
- Mark operation running, commit.
- Run action.
- Mark operation succeeded with `result_summary`, commit.
- On exception, rollback action transaction, mark operation failed with redacted error, commit.
- Use `figure_data.ai.redaction.redact_sensitive_text`.

Required public function:

```python
def run_admin_operation(
    *,
    session_factory: Callable[[], Session],
    operation_id: UUID,
    action: Callable[[Session], dict[str, object]],
    mark_running_fn: Callable[[Session, UUID], None] = mark_admin_operation_running,
    mark_finished_fn: Callable[..., None] = mark_admin_operation_finished,
) -> None:
    ...
```

- [ ] **Step 4: Run runner tests**

Run:

```powershell
uv run --no-sync pytest tests/admin/test_operation_runner.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit runner**

Run:

```powershell
git add src/figure_data/admin/operation_runner.py tests/admin/test_operation_runner.py
git commit -m "feat: 添加后台操作执行器"
```

## Task 2: Add Graph Admin Service

**Files:**
- Create: `src/figure_chain/services/admin_graph.py`
- Modify: `src/figure_chain/schemas.py`
- Create: `tests/figure_chain/test_admin_graph_service.py`

- [ ] **Step 1: Write service tests**

Create `tests/figure_chain/test_admin_graph_service.py` with tests for:

```python
def test_graph_status_includes_latest_batches_and_stale_operations() -> None: ...
def test_validate_encounters_creates_operation_and_background_task() -> None: ...
def test_sync_graph_rebuild_creates_operation_with_cli_preview() -> None: ...
def test_sync_graph_incremental_uses_incremental_operation_type() -> None: ...
def test_validate_graph_requires_neo4j_session() -> None: ...
```

The fake background task object must collect calls:

```python
class FakeBackgroundTasks:
    def __init__(self) -> None:
        self.calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    def add_task(self, func: object, *args: object, **kwargs: object) -> None:
        self.calls.append((func, args, kwargs))
```

- [ ] **Step 2: Run service tests and verify failure**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_graph_service.py -q
```

Expected: fail because `AdminGraphService` does not exist.

- [ ] **Step 3: Add graph schemas**

Append to `src/figure_chain/schemas.py`:

```python
class AdminGraphBatchSummaryResponse(BaseModel):
    id: str
    mode: str
    status: str
    triggered_by: str
    source_watermark: datetime | None
    encounters_seen: int
    relationships_written: int
    relationships_deleted: int
    persons_written: int
    validation_status: str
    validation_summary: dict[str, object]
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class AdminGraphStatusResponse(BaseModel):
    latest_success: AdminGraphBatchSummaryResponse | None
    latest_failed: AdminGraphBatchSummaryResponse | None
    active_encounter_count: int
    path_eligible_encounter_count: int
    stale_running_operations: list[AdminOperationDetailResponse]


class AdminGraphOperationRequest(BaseModel):
    actor: str = Field(default="local", min_length=1, max_length=128)


class AdminGraphSyncRequest(AdminGraphOperationRequest):
    mode: Literal["rebuild", "incremental"]


class AdminGraphOperationResponse(BaseModel):
    operation_id: UUID
    operation_type: str
    status: str
    preview: str
```

- [ ] **Step 4: Implement graph service**

Create `src/figure_chain/services/admin_graph.py`:

- Constructor accepts:
  - `session: Session`
  - `session_factory: sessionmaker[Session]`
  - `neo4j_session: object | None`
  - `background_tasks: BackgroundTasks`
  - injectable function dependencies for tests.
- `get_status() -> AdminGraphStatusResponse`
  - Uses `get_latest_projection_batch(session, status="succeeded")`.
  - Uses `get_latest_projection_batch(session, status="failed")`.
  - Counts active/path eligible encounters from PostgreSQL.
  - Lists stale `running` operations older than 30 minutes using Plan 1 operations repository.
- `start_validate_encounters(request) -> AdminGraphOperationResponse`
  - Creates `admin_operations` with `operation_type="validate_encounters"`.
  - Background action runs `validate_encounters(session)` and returns `{"total": N, "failed": M, "checks": [...]}`.
- `start_sync_graph(request) -> AdminGraphOperationResponse`
  - `mode="rebuild"` calls `sync_graph_rebuild(session, neo4j_session, triggered_by=request.actor)`.
  - `mode="incremental"` calls `sync_graph_incremental(session, neo4j_session, triggered_by=request.actor)`.
- `start_validate_graph(request) -> AdminGraphOperationResponse`
  - Requires Neo4j session.
  - Runs `validate_graph(session, neo4j_session)`.

Raise `ApplicationError(ErrorCode.CONFIGURATION_ERROR, "Neo4j configuration is required")` when sync or validate-graph needs Neo4j but no session is available.

- [ ] **Step 5: Run service tests**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_graph_service.py -q
```

Expected: tests pass.

- [ ] **Step 6: Commit service**

Run:

```powershell
git add src/figure_chain/services/admin_graph.py src/figure_chain/schemas.py tests/figure_chain/test_admin_graph_service.py
git commit -m "feat: 添加后台图同步服务"
```

## Task 3: Add Graph Admin API

**Files:**
- Create: `src/figure_chain/routers/admin_graph.py`
- Modify: `src/figure_chain/dependencies.py`
- Modify: `src/figure_chain/routers/__init__.py`
- Create: `tests/figure_chain/test_admin_graph_api.py`
- Modify: `tests/figure_chain/test_app.py`

- [ ] **Step 1: Write API tests**

Create `tests/figure_chain/test_admin_graph_api.py` asserting:

- `GET /api/v1/admin/graph/status` requires operator role.
- `POST /api/v1/admin/graph/validate-encounters` returns operation id.
- `POST /api/v1/admin/graph/sync` accepts `{"mode": "rebuild", "actor": "local"}`.
- `POST /api/v1/admin/graph/sync` accepts `{"mode": "incremental", "actor": "local"}`.
- `POST /api/v1/admin/graph/validate-graph` returns operation id.

- [ ] **Step 2: Run API tests and verify failure**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_graph_api.py -q
```

Expected: fail because router is not registered.

- [ ] **Step 3: Implement dependency**

Add `get_admin_graph_service` to `src/figure_chain/dependencies.py`. It should receive:

- `Request`
- `BackgroundTasks`
- current `pg_session`
- optional Neo4j session

It should pass `request.app.state.pg_session_factory` into `AdminGraphService` for background task sessions.

- [ ] **Step 4: Implement router**

Create `src/figure_chain/routers/admin_graph.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from figure_chain.access import OperationContext
from figure_chain.dependencies import get_admin_graph_service, require_operator_context
from figure_chain.schemas import (
    AdminGraphOperationRequest,
    AdminGraphOperationResponse,
    AdminGraphStatusResponse,
    AdminGraphSyncRequest,
)
from figure_chain.services.admin_graph import AdminGraphService

router = APIRouter(prefix="/api/v1/admin/graph", tags=["admin"])


@router.get("/status", response_model=AdminGraphStatusResponse)
def get_admin_graph_status(
    service: Annotated[AdminGraphService, Depends(get_admin_graph_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminGraphStatusResponse:
    return service.get_status()


@router.post("/validate-encounters", response_model=AdminGraphOperationResponse)
def validate_admin_encounters(
    request: AdminGraphOperationRequest,
    service: Annotated[AdminGraphService, Depends(get_admin_graph_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminGraphOperationResponse:
    return service.start_validate_encounters(request)


@router.post("/sync", response_model=AdminGraphOperationResponse)
def sync_admin_graph(
    request: AdminGraphSyncRequest,
    service: Annotated[AdminGraphService, Depends(get_admin_graph_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminGraphOperationResponse:
    return service.start_sync_graph(request)


@router.post("/validate-graph", response_model=AdminGraphOperationResponse)
def validate_admin_graph(
    request: AdminGraphOperationRequest,
    service: Annotated[AdminGraphService, Depends(get_admin_graph_service)],
    _context: Annotated[OperationContext, Depends(require_operator_context)],
) -> AdminGraphOperationResponse:
    return service.start_validate_graph(request)
```

- [ ] **Step 5: Register routes**

Update `src/figure_chain/routers/__init__.py` to import and include `admin_graph.router`.

Update `tests/figure_chain/test_app.py`:

```python
assert "/api/v1/admin/graph/status" in route_paths
assert "/api/v1/admin/graph/validate-encounters" in route_paths
assert "/api/v1/admin/graph/sync" in route_paths
assert "/api/v1/admin/graph/validate-graph" in route_paths
```

- [ ] **Step 6: Run API tests**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_graph_api.py tests/figure_chain/test_app.py -q
```

Expected: tests pass.

- [ ] **Step 7: Commit API**

Run:

```powershell
git add src/figure_chain/routers/admin_graph.py src/figure_chain/dependencies.py src/figure_chain/routers/__init__.py tests/figure_chain/test_admin_graph_api.py tests/figure_chain/test_app.py
git commit -m "feat: 添加后台图同步 API"
```

## Task 4: Add Frontend Graph Proxy And Hook

**Files:**
- Create: `frontend/app/api/figure-chain/admin/graph/status/route.ts`
- Create: `frontend/app/api/figure-chain/admin/graph/validate-encounters/route.ts`
- Create: `frontend/app/api/figure-chain/admin/graph/sync/route.ts`
- Create: `frontend/app/api/figure-chain/admin/graph/validate-graph/route.ts`
- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/src/hooks/use-admin-graph.ts`
- Create: `frontend/tests/unit/admin-graph-api-routes.test.ts`

- [ ] **Step 1: Write route tests**

Create `frontend/tests/unit/admin-graph-api-routes.test.ts` asserting each route forwards to the matching FastAPI endpoint and includes operator headers:

```ts
const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};
```

- [ ] **Step 2: Implement route handlers**

Each route handler should call `forwardToFigureChain`:

```ts
return forwardToFigureChain("/api/v1/admin/graph/status", {
  headers: ADMIN_HEADERS,
});
```

POST handlers must pass `method: "POST"` and `body: await request.text()`.

- [ ] **Step 3: Add TypeScript types**

Append:

```ts
export type AdminGraphBatchSummary = {
  id: string;
  mode: string;
  status: string;
  triggered_by: string;
  source_watermark: string | null;
  encounters_seen: number;
  relationships_written: number;
  relationships_deleted: number;
  persons_written: number;
  validation_status: string;
  validation_summary: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
};

export type AdminGraphStatusResponse = {
  latest_success: AdminGraphBatchSummary | null;
  latest_failed: AdminGraphBatchSummary | null;
  active_encounter_count: number;
  path_eligible_encounter_count: number;
  stale_running_operations: AdminOperationDetail[];
};

export type AdminGraphOperationResponse = {
  operation_id: string;
  operation_type: string;
  status: string;
  preview: string;
};
```

- [ ] **Step 4: Add hook**

Create `frontend/src/hooks/use-admin-graph.ts`:

- `useAdminGraphStatus()`
- `useAdminGraphAction()`

`useAdminGraphAction` exposes:

- `validateEncounters(actor: string)`
- `syncGraph(mode: "rebuild" | "incremental", actor: string)`
- `validateGraph(actor: string)`

- [ ] **Step 5: Run frontend tests**

Run:

```powershell
npm --prefix frontend test -- admin-graph-api-routes
npm --prefix frontend run typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 6: Commit proxy and hook**

Run:

```powershell
git add frontend/app/api/figure-chain/admin/graph/status/route.ts frontend/app/api/figure-chain/admin/graph/validate-encounters/route.ts frontend/app/api/figure-chain/admin/graph/sync/route.ts frontend/app/api/figure-chain/admin/graph/validate-graph/route.ts frontend/src/lib/figure-chain-types.ts frontend/src/hooks/use-admin-graph.ts frontend/tests/unit/admin-graph-api-routes.test.ts
git commit -m "feat: 添加后台图同步前端代理"
```

## Task 5: Add Admin Graph Page

**Files:**
- Create: `frontend/app/admin/graph/page.tsx`
- Create: `frontend/src/components/admin-graph-page.tsx`
- Create: `frontend/tests/unit/admin-graph-page.test.tsx`

- [ ] **Step 1: Write page tests**

Create `frontend/tests/unit/admin-graph-page.test.tsx` asserting:

- Status cards show active encounter count and path eligible count.
- Latest successful batch is rendered.
- Latest failed batch is rendered when present.
- Buttons exist for validate encounters, rebuild sync, incremental sync, and validate graph.
- Clicking an action shows returned `operation_id` and preview.
- Stale running operations render links to `/admin/operations?operation_id=...`.

- [ ] **Step 2: Implement component**

Create `frontend/src/components/admin-graph-page.tsx`:

- Use dense admin layout from Plan 1 `AdminShell`.
- Render a compact status panel, batch table, and action panel.
- Action buttons:
  - `Validate encounters`
  - `Sync rebuild`
  - `Sync incremental`
  - `Validate graph`
- Show confirmation text before rebuild:
  - Rebuild clears and rewrites Neo4j projection.
- Show CLI preview from response.
- Link operation id to `/admin/operations?operation_id=${operationId}`.

- [ ] **Step 3: Create page route**

Create `frontend/app/admin/graph/page.tsx`:

```tsx
import { AdminGraphPage } from "@/components/admin-graph-page";

export default function GraphAdminPage() {
  return <AdminGraphPage />;
}
```

- [ ] **Step 4: Run frontend tests**

Run:

```powershell
npm --prefix frontend test -- admin-graph-page
npm --prefix frontend run typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 5: Commit graph page**

Run:

```powershell
git add frontend/app/admin/graph/page.tsx frontend/src/components/admin-graph-page.tsx frontend/tests/unit/admin-graph-page.test.tsx
git commit -m "feat: 添加后台图同步页面"
```

## Task 6: Document And Verify Plan 3

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add:

```md
### 图同步控制台

图同步控制台入口：

```text
http://127.0.0.1:3000/admin/graph
```

该页面可以查看最新 graph projection batch、执行 `validate-encounters`、`sync-graph --rebuild`、`sync-graph --incremental` 和 `validate-graph`。这些动作通过后端 service 执行，不执行浏览器提交的 shell 字符串。
```

- [ ] **Step 2: Run focused verification**

Run:

```powershell
uv run --no-sync pytest tests/admin/test_operation_runner.py tests/figure_chain/test_admin_graph_service.py tests/figure_chain/test_admin_graph_api.py tests/figure_chain/test_app.py -q
npm --prefix frontend test -- admin-graph
npm --prefix frontend run typecheck
```

Expected:

- Backend focused tests pass.
- Frontend graph tests pass.
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
git commit -m "docs: 记录后台图同步控制台"
```

## Final Acceptance

Plan 3 is complete when:

- `/api/v1/admin/graph/status` returns graph batch and encounter status.
- Graph action endpoints create `admin_operations` rows before background execution.
- Operation runner marks success and failure with redacted error messages.
- Sync actions call existing graph projection functions, not shell commands.
- Validate graph records validation summary.
- `/admin/graph` exposes status, action buttons, operation links, and CLI previews.
- Stale running operations are visible.
- Verification commands in Task 6 pass.

## Follow-Up

Plan 4 should add `/admin/jobs` for AI job listing, events, retry/cancel/requeue, queue health, and worker diagnostics.
