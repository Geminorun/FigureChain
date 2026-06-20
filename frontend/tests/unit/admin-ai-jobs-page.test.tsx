import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminAIJobsPage } from "@/components/admin-ai-jobs-page";
import { renderUi } from "@/test/render";

const fetchMock = vi.fn();
const JOB_ID = "00000000-0000-0000-0000-000000000801";
const FAILED_JOB_ID = "00000000-0000-0000-0000-000000000802";
const OPERATION_ID = "00000000-0000-0000-0000-000000000901";

describe("AdminAIJobsPage", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith("/api/figure-chain/admin/ai/health")) {
        return Promise.resolve(
          jsonResponse({
            status_counts: { queued: 2, running: 1 },
            queued_count: 2,
            running_count: 1,
            succeeded_count: 3,
            failed_count: 4,
            cancelled_count: 5,
            stale_running_count: 1,
            oldest_queued_at: "2026-06-20T12:00:00Z",
          }),
        );
      }
      if (url.endsWith(`/${JOB_ID}/events`)) {
        return Promise.resolve(
          jsonResponse({
            items: [
              {
                id: "event-1",
                job_id: JOB_ID,
                event_type: "created",
                actor: "api",
                message: "AI job created",
                metadata: {},
                created_at: "2026-06-20T12:00:00Z",
              },
            ],
            count: 1,
          }),
        );
      }
      if (url.startsWith("/api/figure-chain/admin/ai/jobs") && !init) {
        return Promise.resolve(
          jsonResponse({
            items: [job(JOB_ID, "queued"), job(FAILED_JOB_ID, "failed")],
            count: 2,
            limit: 50,
            offset: 0,
          }),
        );
      }
      if (init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            operation_id: OPERATION_ID,
            operation_type: url.endsWith("/requeue") ? "requeue_ai_jobs" : "cancel_ai_job",
            status: "succeeded",
            job: null,
            result_summary: {},
            preview: url.endsWith("/requeue")
              ? "figure-data requeue-ai-jobs --limit 50"
              : `figure-data cancel-ai-job --job-id ${JOB_ID} --cancelled-by local`,
          }),
        );
      }
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  it("renders health counters, filters, and job table", async () => {
    renderUi(<AdminAIJobsPage />);

    expect((await screen.findAllByText("排队中")).length).toBeGreaterThan(0);
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getAllByText("运行中").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("任务状态")).toBeInTheDocument();
    expect(screen.getByLabelText("目标类型")).toBeInTheDocument();
    expect(screen.getByLabelText("目标 ID")).toBeInTheDocument();
    expect(screen.getByLabelText("队列后端")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: JOB_ID })).toBeInTheDocument();
    expect(screen.getAllByText("candidate:relationship#1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("database").length).toBeGreaterThan(0);
    expect(screen.getAllByText("worker-1").length).toBeGreaterThan(0);
  });

  it("shows events and valid actions after selecting a job", async () => {
    renderUi(<AdminAIJobsPage />);

    await userEvent.click(await screen.findByRole("button", { name: JOB_ID }));

    expect(await screen.findByText("created")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消任务" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重试任务" })).not.toBeInTheDocument();
  });

  it("shows operation id and CLI preview after requeue", async () => {
    renderUi(<AdminAIJobsPage />);

    await screen.findByRole("button", { name: JOB_ID });
    await userEvent.click(screen.getByRole("button", { name: "重新入队可恢复任务" }));

    await waitFor(() => {
      expect(screen.getByText(OPERATION_ID)).toBeInTheDocument();
    });
    expect(screen.getByText("figure-data requeue-ai-jobs --limit 50")).toBeInTheDocument();
  });
});

function job(id: string, status: string) {
  return {
    id,
    job_type: "candidate_review_suggestion",
    target_type: "candidate",
    target_kind: "relationship",
    target_id: 1,
    status,
    created_by: "local",
    params: {},
    result_ref_type: null,
    result_ref_id: null,
    error_code: null,
    error_message: null,
    queue_backend: "database",
    queue_name: null,
    queue_job_id: null,
    enqueued_at: null,
    attempt_count: status === "failed" ? 2 : 0,
    max_attempts: 3,
    next_run_at: null,
    cancel_requested_at: null,
    worker_id: "worker-1",
    heartbeat_at: "2026-06-20T12:00:00Z",
    started_at: null,
    finished_at: null,
    created_at: "2026-06-20T12:00:00Z",
    updated_at: "2026-06-20T12:00:00Z",
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
