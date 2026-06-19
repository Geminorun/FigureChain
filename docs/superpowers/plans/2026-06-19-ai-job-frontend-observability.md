# AI Job Frontend Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose Redis/RQ AI job state clearly in the review workspace so reviewers can understand queued, running, retrying, cancelled, failed, and recovered jobs.

**Architecture:** Extend existing API proxy routes, TypeScript types, hooks, and review components. The UI keeps the existing polling model and adds controls for cancel/retry plus event history; it does not connect to Redis directly.

**Tech Stack:** Next.js, React, TypeScript, existing Fetch API client, Vitest, Playwright.

---

## References

- Foundation plan: `docs/superpowers/plans/2026-06-19-redis-rq-ai-jobs-foundation.md`
- Worker plan: `docs/superpowers/plans/2026-06-19-redis-rq-ai-worker.md`
- Controls plan: `docs/superpowers/plans/2026-06-19-ai-job-controls-recovery.md`
- Existing hook: `frontend/src/hooks/use-ai-job.ts`
- Existing panel: `frontend/src/components/review-ai-panel.tsx`

## Prerequisites

Complete the three backend plans before starting this frontend plan. This plan expects backend responses to include queue metadata and these endpoints:

```text
POST /api/v1/ai/jobs/{job_id}/cancel
POST /api/v1/ai/jobs/{job_id}/retry
GET /api/v1/ai/jobs/{job_id}/events
GET /api/v1/ai/health
```

## File Structure

- Modify `frontend/src/lib/figure-chain-types.ts`: add queue fields, event types, health types.
- Modify `frontend/app/api/figure-chain/ai/jobs/[jobId]/cancel/route.ts`: new proxy route.
- Modify `frontend/app/api/figure-chain/ai/jobs/[jobId]/retry/route.ts`: new proxy route.
- Modify `frontend/app/api/figure-chain/ai/jobs/[jobId]/events/route.ts`: new proxy route.
- Modify `frontend/src/hooks/use-ai-job.ts`: add events, cancel, retry, pollable retry states.
- Modify `frontend/src/components/review-ai-panel.tsx`: display queue metadata, events, retry/cancel controls.
- Test `frontend/tests/unit/review-ai-panel.test.tsx`.
- Test `frontend/tests/unit/use-ai-job.test.tsx`.
- Test `frontend/tests/unit/review-api-routes.test.ts`.
- Test `frontend/tests/e2e/review-workspace.spec.ts`.

### Task 1: Extend Frontend Types

**Files:**
- Modify: `frontend/src/lib/figure-chain-types.ts`
- Test: `frontend/src/test/fixtures.ts`

- [ ] **Step 1: Add AI job queue fields**

Update `AiJobResponse`:

```ts
export type AiJobResponse = {
  id: string;
  job_type: string;
  target_type: string;
  target_kind: string;
  target_id: number;
  status: string;
  created_by: string;
  params: Record<string, unknown>;
  result_ref_type: string | null;
  result_ref_id: string | null;
  error_code: string | null;
  error_message: string | null;
  queue_backend: string;
  queue_name: string | null;
  queue_job_id: string | null;
  enqueued_at: string | null;
  attempt_count: number;
  max_attempts: number;
  next_run_at: string | null;
  cancel_requested_at: string | null;
  worker_id: string | null;
  heartbeat_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};
```

- [ ] **Step 2: Add event and control types**

Add:

```ts
export type AiJobCancelRequest = {
  cancelled_by: string;
};

export type AiJobRetryRequest = {
  created_by: string;
};

export type AiJobEvent = {
  id: string;
  job_id: string;
  event_type: string;
  actor: string;
  message: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type AiJobEventListResponse = {
  items: AiJobEvent[];
  count: number;
};
```

- [ ] **Step 3: Run typecheck**

Run:

```powershell
cd frontend
npm run typecheck
```

Expected: fail until fixtures and tests are updated.

- [ ] **Step 4: Update test fixtures**

Update `frontend/src/test/fixtures.ts` AI job fixtures to include all new fields:

```ts
queue_backend: "rq",
queue_name: "figure-ai",
queue_job_id: "rq-job-501",
enqueued_at: "2026-06-19T00:00:01Z",
attempt_count: 1,
max_attempts: 3,
next_run_at: null,
cancel_requested_at: null,
worker_id: "worker-1",
heartbeat_at: "2026-06-19T00:00:02Z",
```

- [ ] **Step 5: Run typecheck again**

Run:

```powershell
cd frontend
npm run typecheck
```

Expected: pass.

- [ ] **Step 6: Commit Task 1**

```powershell
git add frontend/src/lib/figure-chain-types.ts frontend/src/test/fixtures.ts
git commit -m "feat: 扩展前端 AI job 队列类型"
```

### Task 2: Add Next.js Proxy Routes for Controls and Events

**Files:**
- Create: `frontend/app/api/figure-chain/ai/jobs/[jobId]/cancel/route.ts`
- Create: `frontend/app/api/figure-chain/ai/jobs/[jobId]/retry/route.ts`
- Create: `frontend/app/api/figure-chain/ai/jobs/[jobId]/events/route.ts`
- Test: `frontend/tests/unit/review-api-routes.test.ts`

- [ ] **Step 1: Write route tests**

Add tests to `frontend/tests/unit/review-api-routes.test.ts`:

```ts
it("forwards AI job cancel requests", async () => {
  const { POST } = await import("@/app/api/figure-chain/ai/jobs/[jobId]/cancel/route");
  const request = new Request("http://localhost/api/figure-chain/ai/jobs/job-1/cancel", {
    method: "POST",
    body: JSON.stringify({ cancelled_by: "lyl" }),
  });

  await POST(request, { params: Promise.resolve({ jobId: "job-1" }) });

  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/ai/jobs/job-1/cancel"),
    expect.objectContaining({ method: "POST" }),
  );
});

it("forwards AI job events requests", async () => {
  const { GET } = await import("@/app/api/figure-chain/ai/jobs/[jobId]/events/route");
  const request = new Request("http://localhost/api/figure-chain/ai/jobs/job-1/events");

  await GET(request, { params: Promise.resolve({ jobId: "job-1" }) });

  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/ai/jobs/job-1/events"),
    expect.any(Object),
  );
});
```

- [ ] **Step 2: Run failing route tests**

Run:

```powershell
cd frontend
npm run test -- review-api-routes.test.ts
```

Expected: fail because proxy routes do not exist.

- [ ] **Step 3: Add cancel proxy route**

Create `frontend/app/api/figure-chain/ai/jobs/[jobId]/cancel/route.ts`:

```ts
import { forwardToFigureChain } from "@/app/api/figure-chain/_proxy";

type RouteContext = {
  params: Promise<{ jobId: string }>;
};

export async function POST(request: Request, context: RouteContext) {
  const { jobId } = await context.params;
  return forwardToFigureChain(`/api/v1/ai/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
    body: await request.text(),
  });
}
```

- [ ] **Step 4: Add retry proxy route**

Create `frontend/app/api/figure-chain/ai/jobs/[jobId]/retry/route.ts`:

```ts
import { forwardToFigureChain } from "@/app/api/figure-chain/_proxy";

type RouteContext = {
  params: Promise<{ jobId: string }>;
};

export async function POST(request: Request, context: RouteContext) {
  const { jobId } = await context.params;
  return forwardToFigureChain(`/api/v1/ai/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: "POST",
    body: await request.text(),
  });
}
```

- [ ] **Step 5: Add events proxy route**

Create `frontend/app/api/figure-chain/ai/jobs/[jobId]/events/route.ts`:

```ts
import { forwardToFigureChain } from "@/app/api/figure-chain/_proxy";

type RouteContext = {
  params: Promise<{ jobId: string }>;
};

export async function GET(_request: Request, context: RouteContext) {
  const { jobId } = await context.params;
  return forwardToFigureChain(`/api/v1/ai/jobs/${encodeURIComponent(jobId)}/events`);
}
```

- [ ] **Step 6: Run route tests**

Run:

```powershell
cd frontend
npm run test -- review-api-routes.test.ts
```

Expected: pass.

- [ ] **Step 7: Commit Task 2**

```powershell
git add frontend/app/api/figure-chain/ai/jobs frontend/tests/unit/review-api-routes.test.ts
git commit -m "feat: 增加 AI job 控制代理路由"
```

### Task 3: Extend `useAiJob`

**Files:**
- Modify: `frontend/src/hooks/use-ai-job.ts`
- Test: `frontend/tests/unit/use-ai-job.test.tsx`

- [ ] **Step 1: Write hook tests**

Add tests:

```tsx
it("cancels the active AI job", async () => {
  fetchMock.mockResponseOnce(JSON.stringify(jobListResponse));
  fetchMock.mockResponseOnce(JSON.stringify(activeJob));

  const { result } = renderHook(() =>
    useAiJob({ targetType: "candidate", targetKind: "relationship", targetId: 960698 }),
  );

  await waitFor(() => expect(result.current.jobs.length).toBe(1));
  await act(async () => {
    await result.current.cancelJob(activeJob.id, { cancelledBy: "lyl" });
  });

  expect(fetchMock).toHaveBeenCalledWith(
    `/api/figure-chain/ai/jobs/${activeJob.id}/cancel`,
    expect.objectContaining({ method: "POST" }),
  );
});

it("loads AI job events", async () => {
  fetchMock.mockResponseOnce(JSON.stringify(jobListResponse));
  fetchMock.mockResponseOnce(JSON.stringify({ items: [], count: 0 }));

  const { result } = renderHook(() =>
    useAiJob({ targetType: "candidate", targetKind: "relationship", targetId: 960698 }),
  );

  await waitFor(() => expect(result.current.jobs.length).toBe(1));
  await act(async () => {
    await result.current.loadEvents(activeJob.id);
  });

  expect(fetchMock).toHaveBeenCalledWith(`/api/figure-chain/ai/jobs/${activeJob.id}/events`);
});
```

- [ ] **Step 2: Run failing hook tests**

Run:

```powershell
cd frontend
npm run test -- use-ai-job.test.tsx
```

Expected: fail because `cancelJob` and `loadEvents` are missing.

- [ ] **Step 3: Extend hook result type**

Update `UseAiJobResult`:

```ts
export type UseAiJobResult = AiJobState & {
  refresh: () => void;
  createJob: (options: CreateAiJobOptions) => Promise<AiJobResponse | null>;
  cancelJob: (jobId: string, options: { cancelledBy: string }) => Promise<AiJobResponse | null>;
  retryJob: (jobId: string, options: { createdBy: string }) => Promise<AiJobResponse | null>;
  loadEvents: (jobId: string) => Promise<AiJobEvent[]>;
};
```

Update `AiJobState`:

```ts
eventsByJobId: Record<string, AiJobEvent[]>;
```

- [ ] **Step 4: Add pollable statuses**

Update:

```ts
const POLLABLE_STATUSES = new Set(["queued", "running"]);
```

to:

```ts
const POLLABLE_STATUSES = new Set(["queued", "running"]);
```

Keep polling limited to statuses that can change without user action. A job with `next_run_at` remains `queued`, so no new poll status is needed.

- [ ] **Step 5: Implement control methods**

Add helper:

```ts
async function postJobAction(
  jobId: string,
  action: "cancel" | "retry",
  body: Record<string, string>,
): Promise<AiJobResponse> {
  const response = await fetch(`/api/figure-chain/ai/jobs/${encodeURIComponent(jobId)}/${action}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  const payload = (await response.json()) as unknown;
  if (!response.ok) {
    throw parseErrorResponse(payload);
  }
  return payload as AiJobResponse;
}
```

Implement `cancelJob`, `retryJob`, and `loadEvents` using the existing `replaceJob()` helper.

- [ ] **Step 6: Run hook tests**

Run:

```powershell
cd frontend
npm run test -- use-ai-job.test.tsx
```

Expected: pass.

- [ ] **Step 7: Commit Task 3**

```powershell
git add frontend/src/hooks/use-ai-job.ts frontend/tests/unit/use-ai-job.test.tsx
git commit -m "feat: 扩展 AI job 前端控制 hook"
```

### Task 4: Update Review AI Panel

**Files:**
- Modify: `frontend/src/components/review-ai-panel.tsx`
- Test: `frontend/tests/unit/review-ai-panel.test.tsx`

- [ ] **Step 1: Write component tests**

Add tests:

```tsx
it("shows queue metadata for a running job", () => {
  render(
    <ReviewAiPanel
      activeJob={{ ...activeJob, queue_backend: "rq", worker_id: "worker-1", attempt_count: 1, max_attempts: 3 }}
      detail={candidateDetail}
      error={null}
      isCreating={false}
      jobs={[activeJob]}
      eventsByJobId={{}}
      onCreateJob={vi.fn()}
      onRefreshCandidate={vi.fn()}
      onCancelJob={vi.fn()}
      onRetryJob={vi.fn()}
      onLoadEvents={vi.fn()}
    />,
  );

  expect(screen.getByText(/rq/)).toBeInTheDocument();
  expect(screen.getByText(/worker-1/)).toBeInTheDocument();
  expect(screen.getByText(/1\/3/)).toBeInTheDocument();
});

it("offers retry for failed job", () => {
  render(
    <ReviewAiPanel
      activeJob={{ ...activeJob, status: "failed", error_message: "timeout" }}
      detail={candidateDetail}
      error={null}
      isCreating={false}
      jobs={[{ ...activeJob, status: "failed", error_message: "timeout" }]}
      eventsByJobId={{}}
      onCreateJob={vi.fn()}
      onRefreshCandidate={vi.fn()}
      onCancelJob={vi.fn()}
      onRetryJob={vi.fn()}
      onLoadEvents={vi.fn()}
    />,
  );

  expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run failing component tests**

Run:

```powershell
cd frontend
npm run test -- review-ai-panel.test.tsx
```

Expected: fail because props and UI are not updated.

- [ ] **Step 3: Extend component props**

Update `ReviewAiPanelProps`:

```ts
  eventsByJobId: Record<string, AiJobEvent[]>;
  onCancelJob: (jobId: string, options: { cancelledBy: string }) => Promise<AiJobResponse | null>;
  onRetryJob: (jobId: string, options: { createdBy: string }) => Promise<AiJobResponse | null>;
  onLoadEvents: (jobId: string) => Promise<AiJobEvent[]>;
```

- [ ] **Step 4: Add job metadata rendering**

Inside each history item, render:

```tsx
<p className="text-stone-600">
  queue {job.queue_backend ?? "database"} / attempt{" "}
  {"attempt_count" in job ? `${job.attempt_count}/${job.max_attempts}` : "unknown"}
</p>
{"worker_id" in job && job.worker_id ? (
  <p className="break-all text-stone-600">worker {job.worker_id}</p>
) : null}
{"next_run_at" in job && job.next_run_at ? (
  <p className="text-stone-600">next retry {job.next_run_at}</p>
) : null}
```

- [ ] **Step 5: Add cancel and retry buttons**

For active queued/running jobs:

```tsx
<button
  className="inline-flex min-h-9 items-center rounded border border-stone-300 px-3 py-1.5 text-sm text-stone-800 hover:bg-stone-50"
  type="button"
  onClick={() => activeJob ? onCancelJob(activeJob.id, { cancelledBy: createdBy.trim() || "local" }) : undefined}
>
  Cancel
</button>
```

For failed jobs:

```tsx
<button
  className="inline-flex min-h-9 items-center rounded border border-stone-300 px-3 py-1.5 text-sm text-stone-800 hover:bg-stone-50"
  type="button"
  onClick={() => onRetryJob(jobId(job), { createdBy: createdBy.trim() || "local" })}
>
  Retry
</button>
```

- [ ] **Step 6: Run component tests**

Run:

```powershell
cd frontend
npm run test -- review-ai-panel.test.tsx
```

Expected: pass.

- [ ] **Step 7: Commit Task 4**

```powershell
git add frontend/src/components/review-ai-panel.tsx frontend/tests/unit/review-ai-panel.test.tsx
git commit -m "feat: 展示 AI job 队列状态"
```

### Task 5: Wire Review Workspace and E2E Smoke

**Files:**
- Modify: `frontend/src/components/review-workspace.tsx`
- Test: `frontend/tests/e2e/review-workspace.spec.ts`

- [ ] **Step 1: Pass hook methods into panel**

In `ReviewWorkspace`, pass:

```tsx
<ReviewAiPanel
  activeJob={aiJob.activeJob}
  detail={detail.detail}
  error={aiJob.error}
  isCreating={aiJob.isCreating}
  jobs={aiJob.jobs}
  eventsByJobId={aiJob.eventsByJobId}
  onCreateJob={aiJob.createJob}
  onRefreshCandidate={detail.refresh}
  onCancelJob={aiJob.cancelJob}
  onRetryJob={aiJob.retryJob}
  onLoadEvents={aiJob.loadEvents}
/>
```

- [ ] **Step 2: Update E2E mock job payload**

In `frontend/tests/e2e/review-workspace.spec.ts`, update AI job mock objects with:

```ts
queue_backend: "rq",
queue_name: "figure-ai",
queue_job_id: "rq-job-501",
enqueued_at: "2026-06-19T00:00:01Z",
attempt_count: 1,
max_attempts: 3,
next_run_at: null,
cancel_requested_at: null,
worker_id: "worker-1",
heartbeat_at: "2026-06-19T00:00:02Z",
```

- [ ] **Step 3: Run frontend unit tests**

Run:

```powershell
cd frontend
npm run test
```

Expected: pass.

- [ ] **Step 4: Run frontend checks**

Run:

```powershell
cd frontend
npm run lint
npm run typecheck
```

Expected: both pass.

- [ ] **Step 5: Run e2e smoke**

Run:

```powershell
cd frontend
npm run e2e -- review-workspace.spec.ts
```

Expected: pass.

- [ ] **Step 6: Commit Task 5**

```powershell
git add frontend/src/components/review-workspace.tsx frontend/tests/e2e/review-workspace.spec.ts
git commit -m "feat: 接入 AI job 前端可观测性"
```

## Plan 4 Final Verification

- [ ] Run all frontend checks:

```powershell
cd frontend
npm run test
npm run lint
npm run typecheck
npm run build
```

Expected: all pass.

- [ ] Run review e2e smoke:

```powershell
cd frontend
npm run e2e -- review-workspace.spec.ts
```

Expected: pass.
