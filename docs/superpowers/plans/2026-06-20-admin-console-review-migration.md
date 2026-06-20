# Admin Console Review Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有候选审核工作台迁入 `/admin/review`，并让 promote、reject、needs-review、retract encounter 这些人工维护动作写入 `admin_operations`。

**Architecture:** 后端新增 `AdminReviewService` 包装现有 `ReviewService` 和 `figure_data.encounters.retraction.retract_encounter`，避免复制审核与 Encounter 业务逻辑。前端复用现有 review 组件，通过可配置 API base path 调用 Admin review route handlers；旧 `/review` 入口重定向到 `/admin/review`。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Pydantic v2, pytest, mypy, ruff, Next.js 16, React 19, TypeScript, Vitest, Playwright optional smoke。

---

## Preconditions

- Plan 1 已完成并提供 `admin_operations`。
- Plan 2 已完成并提供 `/admin/data` 关联跳转到 `/admin/review`。
- 现有审核能力可复用：
  - `src/figure_chain/services/review.py`
  - `src/figure_chain/routers/review.py`
  - `src/figure_data.encounters.promotion.promote_candidate_to_encounter`
  - `src/figure_data.review.candidate_status.reject_candidate`
  - `src/figure_data.review.candidate_status.mark_candidate_for_review`
  - `src/figure_data.encounters.retraction.retract_encounter`
- 本计划不改 AI 候选建议生成逻辑。

## Scope

本计划覆盖：

- Admin review API wrapper。
- Review action operation recording。
- Encounter retract API and UI action。
- `/admin/review` 页面。
- Legacy `/review` redirect。
- Frontend review hooks configurable API base path。
- Existing review tests迁移到 admin path。

本计划不覆盖：

- 新候选生成规则。
- 新 Encounter promotion policy。
- 自动审核。
- Neo4j 自动同步；提升或撤回后用户从 `/admin/graph` 手动同步。

## Operation Types

Plan 5 使用以下 `admin_operations.operation_type`：

```text
promote_candidate
reject_candidate
mark_candidate_needs_review
retract_encounter
```

AI job create/cancel/retry 仍由现有 AI job API 或 Plan 4 `/admin/jobs` 负责。

## File Structure

### Backend

- Create: `src/figure_chain/services/admin_review.py`
  - Admin wrapper for review actions and encounter retract.
- Create: `src/figure_chain/routers/admin_review.py`
  - Admin review endpoints.
- Modify: `src/figure_chain/dependencies.py`
  - Add `get_admin_review_service`.
- Modify: `src/figure_chain/routers/__init__.py`
  - Include admin review router.
- Modify: `src/figure_chain/schemas.py`
  - Admin review action and retract responses.
- Modify: `src/figure_chain/services/encounters.py`
  - Add retract method only if tests prove the service boundary is useful.

### Tests

- Create: `tests/figure_chain/test_admin_review_service.py`
- Create: `tests/figure_chain/test_admin_review_api.py`
- Modify: `tests/figure_chain/test_app.py`
- Keep existing `tests/figure_chain/test_review_service.py` and `tests/figure_chain/test_review_api.py` passing.

### Frontend

- Create: `frontend/app/admin/review/page.tsx`
- Modify: `frontend/app/review/page.tsx`
- Create: `frontend/app/api/figure-chain/admin/review/candidates/route.ts`
- Create: `frontend/app/api/figure-chain/admin/review/candidates/[kind]/[candidateId]/route.ts`
- Create: `frontend/app/api/figure-chain/admin/review/candidates/[kind]/[candidateId]/promote/route.ts`
- Create: `frontend/app/api/figure-chain/admin/review/candidates/[kind]/[candidateId]/reject/route.ts`
- Create: `frontend/app/api/figure-chain/admin/review/candidates/[kind]/[candidateId]/needs-review/route.ts`
- Create: `frontend/app/api/figure-chain/admin/review/encounters/[encounterId]/retract/route.ts`
- Modify: `frontend/src/hooks/use-review-candidates.ts`
- Modify: `frontend/src/hooks/use-review-candidate-detail.ts`
- Modify: `frontend/src/hooks/use-review-actions.ts`
- Create: `frontend/src/hooks/use-admin-review-actions.ts`
- Modify: `frontend/src/components/review-workspace.tsx`
- Create: `frontend/src/components/admin-review-workspace.tsx`
- Modify: `frontend/src/components/review-action-panel.tsx`
- Create: `frontend/tests/unit/admin-review-api-routes.test.ts`
- Create: `frontend/tests/unit/admin-review-workspace.test.tsx`
- Modify: `frontend/tests/e2e/review-workspace.spec.ts`

### Docs

- Modify: `README.md`

## Task 1: Add Admin Review Service With Operation Recording

**Files:**
- Create: `src/figure_chain/services/admin_review.py`
- Modify: `src/figure_chain/schemas.py`
- Create: `tests/figure_chain/test_admin_review_service.py`

- [ ] **Step 1: Write service tests**

Create `tests/figure_chain/test_admin_review_service.py` with:

```python
def test_admin_review_service_lists_candidates_through_review_service() -> None: ...
def test_admin_review_service_gets_candidate_through_review_service() -> None: ...
def test_admin_review_service_records_promote_operation() -> None: ...
def test_admin_review_service_records_reject_operation() -> None: ...
def test_admin_review_service_records_needs_review_operation() -> None: ...
def test_admin_review_service_records_retract_operation() -> None: ...
def test_admin_review_service_marks_operation_failed_when_action_fails() -> None: ...
```

For promote, assert:

```python
operation_type == "promote_candidate"
related_resource_type == "candidate"
related_resource_id == "relationship:960655"
```

For retract, assert:

```python
operation_type == "retract_encounter"
related_resource_type == "encounter"
related_resource_id == str(encounter_id)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_review_service.py -q
```

Expected: fail because `AdminReviewService` does not exist.

- [ ] **Step 3: Add schemas**

Append to `src/figure_chain/schemas.py`:

```python
class AdminReviewActionResponse(BaseModel):
    operation_id: UUID
    operation_type: str
    status: str
    action: ReviewActionResponse
    preview: str


class AdminEncounterRetractRequest(BaseModel):
    reviewed_by: str = Field(min_length=1)
    note: str = Field(min_length=1)
    force: bool = False


class AdminEncounterRetractResultResponse(BaseModel):
    encounter_id: UUID
    status: str
    path_eligible: bool
    linked_candidates_updated: int


class AdminEncounterRetractResponse(BaseModel):
    operation_id: UUID
    operation_type: str
    status: str
    result: AdminEncounterRetractResultResponse
    preview: str
```

- [ ] **Step 4: Implement service**

Create `src/figure_chain/services/admin_review.py`:

- Constructor accepts:
  - `session: Session`
  - `review_service: ReviewService | None = None`
  - `retract_encounter_fn = retract_encounter`
  - operation repository functions from Plan 1.
- Query methods:
  - `list_candidates(filters)` delegates to `ReviewService.list_candidates`.
  - `get_candidate(kind, candidate_id)` delegates to `ReviewService.get_candidate`.
- Action methods:
  - `promote_candidate(kind, candidate_id, request)`
  - `reject_candidate(kind, candidate_id, request)`
  - `mark_candidate_needs_review(kind, candidate_id, request)`
  - `retract_encounter(encounter_id, request)`
- For each action:
  - create operation with sanitized request payload;
  - call existing review or encounter function;
  - mark operation succeeded with result summary;
  - on exception, mark operation failed and re-raise.

Preview strings:

```text
figure-data promote-encounter --kind relationship --id 960655 --reviewed-by local
figure-data reject-candidate --kind relationship --id 960655 --reviewed-by local
figure-data mark-candidate-review --kind relationship --id 960655 --reviewed-by local
figure-data retract-encounter --encounter-id <uuid> --reviewed-by local
```

- [ ] **Step 5: Run service tests**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_review_service.py -q
```

Expected: tests pass.

- [ ] **Step 6: Commit service**

Run:

```powershell
git add src/figure_chain/services/admin_review.py src/figure_chain/schemas.py tests/figure_chain/test_admin_review_service.py
git commit -m "feat: 添加后台审核操作服务"
```

## Task 2: Add Admin Review API

**Files:**
- Create: `src/figure_chain/routers/admin_review.py`
- Modify: `src/figure_chain/dependencies.py`
- Modify: `src/figure_chain/routers/__init__.py`
- Create: `tests/figure_chain/test_admin_review_api.py`
- Modify: `tests/figure_chain/test_app.py`

- [ ] **Step 1: Write API tests**

Create tests:

```python
def test_admin_review_api_requires_operator_role() -> None: ...
def test_admin_review_api_lists_candidates() -> None: ...
def test_admin_review_api_gets_candidate() -> None: ...
def test_admin_review_api_promotes_candidate() -> None: ...
def test_admin_review_api_rejects_candidate() -> None: ...
def test_admin_review_api_marks_candidate_needs_review() -> None: ...
def test_admin_review_api_retracts_encounter() -> None: ...
```

Use headers:

```python
{"x-figure-role": "operator", "x-figure-actor": "local"}
```

- [ ] **Step 2: Run API tests and verify failure**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_review_api.py -q
```

Expected: fail because admin review router is not registered.

- [ ] **Step 3: Add dependency**

Add `get_admin_review_service` to `src/figure_chain/dependencies.py`:

```python
def get_admin_review_service(
    pg_session: Annotated[Session, Depends(get_pg_session)],
) -> AdminReviewService:
    return AdminReviewService(pg_session)
```

- [ ] **Step 4: Implement router**

Create `src/figure_chain/routers/admin_review.py` with prefix `/api/v1/admin/review`.

Routes:

```text
GET  /candidates
GET  /candidates/{kind}/{candidate_id}
POST /candidates/{kind}/{candidate_id}/promote
POST /candidates/{kind}/{candidate_id}/reject
POST /candidates/{kind}/{candidate_id}/needs-review
POST /encounters/{encounter_id}/retract
```

All routes require `require_operator_context`.

List/detail routes return the same response models as existing review API.
Action routes return admin action response models containing `operation_id` and `preview`.

- [ ] **Step 5: Register routes and update app tests**

Update `src/figure_chain/routers/__init__.py` to include `admin_review.router`.

Update `tests/figure_chain/test_app.py`:

```python
assert "/api/v1/admin/review/candidates" in route_paths
assert "/api/v1/admin/review/candidates/{kind}/{candidate_id}" in route_paths
assert "/api/v1/admin/review/candidates/{kind}/{candidate_id}/promote" in route_paths
assert "/api/v1/admin/review/candidates/{kind}/{candidate_id}/reject" in route_paths
assert "/api/v1/admin/review/candidates/{kind}/{candidate_id}/needs-review" in route_paths
assert "/api/v1/admin/review/encounters/{encounter_id}/retract" in route_paths
```

- [ ] **Step 6: Run API tests**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_review_api.py tests/figure_chain/test_app.py -q
```

Expected: tests pass.

- [ ] **Step 7: Commit API**

Run:

```powershell
git add src/figure_chain/routers/admin_review.py src/figure_chain/dependencies.py src/figure_chain/routers/__init__.py tests/figure_chain/test_admin_review_api.py tests/figure_chain/test_app.py
git commit -m "feat: 添加后台审核 API"
```

## Task 3: Add Frontend Admin Review Proxy

**Files:**
- Create: `frontend/app/api/figure-chain/admin/review/candidates/route.ts`
- Create: `frontend/app/api/figure-chain/admin/review/candidates/[kind]/[candidateId]/route.ts`
- Create: `frontend/app/api/figure-chain/admin/review/candidates/[kind]/[candidateId]/promote/route.ts`
- Create: `frontend/app/api/figure-chain/admin/review/candidates/[kind]/[candidateId]/reject/route.ts`
- Create: `frontend/app/api/figure-chain/admin/review/candidates/[kind]/[candidateId]/needs-review/route.ts`
- Create: `frontend/app/api/figure-chain/admin/review/encounters/[encounterId]/retract/route.ts`
- Modify: `frontend/src/lib/figure-chain-types.ts`
- Create: `frontend/tests/unit/admin-review-api-routes.test.ts`

- [ ] **Step 1: Write route tests**

Create `frontend/tests/unit/admin-review-api-routes.test.ts` asserting:

- Candidate list query keys match existing review list keys.
- Dynamic kind/candidate id paths are forwarded correctly.
- Promote/reject/needs-review/retract POST bodies are forwarded unchanged.
- Operator headers are present.

- [ ] **Step 2: Implement route handlers**

Use the existing review route handlers as reference, but forward to `/api/v1/admin/review/...` and include:

```ts
const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};
```

- [ ] **Step 3: Add TypeScript response types**

Append:

```ts
export type AdminReviewActionResponse = {
  operation_id: string;
  operation_type: string;
  status: string;
  action: ReviewActionResponse;
  preview: string;
};

export type AdminEncounterRetractResponse = {
  operation_id: string;
  operation_type: string;
  status: string;
  result: {
    encounter_id: string;
    status: string;
    path_eligible: boolean;
    linked_candidates_updated: number;
  };
  preview: string;
};
```

- [ ] **Step 4: Run route tests**

Run:

```powershell
npm --prefix frontend test -- admin-review-api-routes
npm --prefix frontend run typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 5: Commit proxy**

Run:

```powershell
git add frontend/app/api/figure-chain/admin/review frontend/src/lib/figure-chain-types.ts frontend/tests/unit/admin-review-api-routes.test.ts
git commit -m "feat: 添加后台审核前端代理"
```

## Task 4: Refactor Review Hooks For Admin Base Path

**Files:**
- Modify: `frontend/src/hooks/use-review-candidates.ts`
- Modify: `frontend/src/hooks/use-review-candidate-detail.ts`
- Modify: `frontend/src/hooks/use-review-actions.ts`
- Create: `frontend/src/hooks/use-admin-review-actions.ts`
- Modify: `frontend/tests/unit/review-hooks.test.tsx`

- [ ] **Step 1: Update hook tests**

Add tests asserting hooks can use custom base paths:

```ts
useReviewCandidates(filters, { apiBasePath: "/api/figure-chain/admin/review" })
useReviewCandidateDetail("relationship", 960655, { apiBasePath: "/api/figure-chain/admin/review" })
useReviewActions(target, { apiBasePath: "/api/figure-chain/admin/review" })
```

Expected fetch URLs:

```text
/api/figure-chain/admin/review/candidates
/api/figure-chain/admin/review/candidates/relationship/960655
/api/figure-chain/admin/review/candidates/relationship/960655/promote
```

- [ ] **Step 2: Run hook tests and verify failure**

Run:

```powershell
npm --prefix frontend test -- review-hooks
```

Expected: fail because hooks do not accept an `apiBasePath` option.

- [ ] **Step 3: Refactor hooks**

Add an optional second parameter to each hook:

```ts
type ReviewApiOptions = {
  apiBasePath?: string;
};

const DEFAULT_REVIEW_API_BASE_PATH = "/api/figure-chain/review";
```

Use `options.apiBasePath ?? DEFAULT_REVIEW_API_BASE_PATH` when building fetch URLs.

- [ ] **Step 4: Add admin action hook**

Create `frontend/src/hooks/use-admin-review-actions.ts`:

- Wrap `useReviewActions(target, { apiBasePath: "/api/figure-chain/admin/review" })`.
- Add `retractEncounter(encounterId, request)` that posts to `/api/figure-chain/admin/review/encounters/{encounterId}/retract`.

- [ ] **Step 5: Run hook tests**

Run:

```powershell
npm --prefix frontend test -- review-hooks
npm --prefix frontend run typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 6: Commit hook refactor**

Run:

```powershell
git add frontend/src/hooks/use-review-candidates.ts frontend/src/hooks/use-review-candidate-detail.ts frontend/src/hooks/use-review-actions.ts frontend/src/hooks/use-admin-review-actions.ts frontend/tests/unit/review-hooks.test.tsx
git commit -m "refactor: 支持审核工作台切换后台 API"
```

## Task 5: Add Admin Review Workspace And Legacy Redirect

**Files:**
- Create: `frontend/app/admin/review/page.tsx`
- Modify: `frontend/app/review/page.tsx`
- Modify: `frontend/src/components/review-workspace.tsx`
- Create: `frontend/src/components/admin-review-workspace.tsx`
- Modify: `frontend/src/components/review-action-panel.tsx`
- Create: `frontend/tests/unit/admin-review-workspace.test.tsx`
- Modify: `frontend/tests/unit/review-workspace.test.tsx`
- Modify: `frontend/tests/e2e/review-workspace.spec.ts`

- [ ] **Step 1: Write workspace tests**

Create `frontend/tests/unit/admin-review-workspace.test.tsx` asserting:

- Admin page renders candidate list and detail areas.
- Admin page fetches `/api/figure-chain/admin/review/candidates`.
- Promote uses admin endpoint and renders operation id after success.
- Retract encounter button renders only when candidate detail includes a linked encounter.
- Legacy `/review` page redirects to `/admin/review`.

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
npm --prefix frontend test -- admin-review-workspace review-workspace
```

Expected: fail because admin review workspace does not exist.

- [ ] **Step 3: Refactor ReviewWorkspace**

Modify `frontend/src/components/review-workspace.tsx`:

- Add props:

```ts
type ReviewWorkspaceProps = {
  reviewApiBasePath?: string;
  mode?: "review" | "admin";
};
```

- Pass `reviewApiBasePath` to review hooks.
- In admin mode, use `useAdminReviewActions`.
- Preserve existing default behavior for non-admin imports.

- [ ] **Step 4: Add retract UI**

Modify `frontend/src/components/review-action-panel.tsx`:

- Add optional prop:

```ts
onRetractEncounter?: (request: { encounterId: string; reviewed_by: string; note: string; force: boolean }) => Promise<unknown>;
```

- Render retract control when:
  - `detail.linked_encounter` exists, or equivalent existing detail field names expose promoted encounter.
- Require note before submitting.
- Show returned operation id and preview if available.

- [ ] **Step 5: Create admin workspace and page**

Create `frontend/src/components/admin-review-workspace.tsx`:

```tsx
import { ReviewWorkspace } from "@/components/review-workspace";

export function AdminReviewWorkspace() {
  return (
    <ReviewWorkspace
      mode="admin"
      reviewApiBasePath="/api/figure-chain/admin/review"
    />
  );
}
```

Create `frontend/app/admin/review/page.tsx`:

```tsx
import { AdminReviewWorkspace } from "@/components/admin-review-workspace";

export default function AdminReviewPage() {
  return <AdminReviewWorkspace />;
}
```

- [ ] **Step 6: Redirect legacy page**

Modify `frontend/app/review/page.tsx`:

```tsx
import { redirect } from "next/navigation";

export default function ReviewPage() {
  redirect("/admin/review");
}
```

- [ ] **Step 7: Update e2e path**

Modify `frontend/tests/e2e/review-workspace.spec.ts` to start from:

```ts
await page.goto("/admin/review");
```

Keep one assertion that `/review` redirects to `/admin/review`.

- [ ] **Step 8: Run frontend tests**

Run:

```powershell
npm --prefix frontend test -- admin-review-workspace review-workspace review-hooks
npm --prefix frontend run typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 9: Commit workspace migration**

Run:

```powershell
git add frontend/app/admin/review/page.tsx frontend/app/review/page.tsx frontend/src/components/review-workspace.tsx frontend/src/components/admin-review-workspace.tsx frontend/src/components/review-action-panel.tsx frontend/tests/unit/admin-review-workspace.test.tsx frontend/tests/unit/review-workspace.test.tsx frontend/tests/e2e/review-workspace.spec.ts
git commit -m "feat: 迁移审核工作台到后台"
```

## Task 6: Document And Verify Plan 5

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add:

```md
### 审核工作台

后台审核工作台入口：

```text
http://127.0.0.1:3000/admin/review
```

候选提升、拒绝、标记待复核和 Encounter 撤回都会记录到 `admin_operations`。旧 `/review` 入口会跳转到 `/admin/review`。
```

- [ ] **Step 2: Run focused verification**

Run:

```powershell
uv run --no-sync pytest tests/figure_chain/test_admin_review_service.py tests/figure_chain/test_admin_review_api.py tests/figure_chain/test_review_service.py tests/figure_chain/test_review_api.py tests/figure_chain/test_app.py -q
npm --prefix frontend test -- admin-review review-workspace review-hooks
npm --prefix frontend run typecheck
```

Expected:

- Backend admin review and legacy review tests pass.
- Frontend admin review and existing review tests pass.
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

- [ ] **Step 4: Optional browser smoke**

If local API and frontend dev server are already running, run:

```powershell
npm --prefix frontend run test:e2e -- review-workspace
```

Expected:

- `/admin/review` loads.
- Candidate list renders.
- Existing mocked review flow passes.

- [ ] **Step 5: Commit docs**

Run:

```powershell
git add README.md
git commit -m "docs: 记录后台审核工作台"
```

## Final Acceptance

Plan 5 is complete when:

- `/api/v1/admin/review/candidates` and detail endpoints work.
- Admin promote/reject/needs-review endpoints write `admin_operations`.
- Admin encounter retract endpoint writes `admin_operations`.
- Existing non-admin review API still passes tests.
- `/admin/review` renders the review workspace using admin API routes.
- `/review` redirects to `/admin/review`.
- Review action success UI shows operation id and CLI preview.
- Verification commands in Task 6 pass.

## Final Admin Console Acceptance

After Plans 1-5:

- `/admin/data` supports white-listed resource querying.
- `/admin/graph` supports graph status, validate, sync, and validation.
- `/admin/jobs` supports AI job observability and recovery actions.
- `/admin/review` supports candidate review and Encounter retraction with operation history.
- `/admin/operations` provides the cross-cutting audit trail.
- The browser never sends arbitrary SQL or shell strings.
- PostgreSQL remains the source of truth and Neo4j remains a rebuildable projection.
