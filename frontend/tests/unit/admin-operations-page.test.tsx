import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminOperationsPage } from "@/components/admin-operations-page";

const fetchMock = vi.fn();
const operationIdSearchParamMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({
    get: operationIdSearchParamMock,
  }),
}));

beforeEach(() => {
  fetchMock.mockReset();
  global.fetch = fetchMock;
  operationIdSearchParamMock.mockReturnValue(null);
});

describe("AdminOperationsPage", () => {
  it("renders operation history rows", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          items: [
            {
              operation_id: "00000000-0000-0000-0000-000000000601",
              operation_type: "sync_graph_rebuild",
              actor: "lyl",
              status: "succeeded",
              request_payload: { mode: "rebuild" },
              result_summary: { relationships_written: 10 },
              error_message: null,
              related_resource_type: "graph_projection_batch",
              related_resource_id: "batch-1",
              started_at: "2026-06-20T12:00:00Z",
              finished_at: "2026-06-20T12:01:00Z",
              created_at: "2026-06-20T12:00:00Z",
              updated_at: "2026-06-20T12:01:00Z",
            },
          ],
          limit: 50,
          offset: 0,
          count: 1,
        }),
        { status: 200 },
      ),
    );

    render(<AdminOperationsPage />);

    expect(await screen.findByText("sync_graph_rebuild")).toBeInTheDocument();
    expect(screen.getByText("succeeded")).toBeInTheDocument();
    expect(screen.getByText("lyl")).toBeInTheDocument();
    expect(screen.getByText(/relationships_written/)).toBeInTheDocument();
  });

  it("shows API errors", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ error: { code: "admin_error", message: "down" } }),
        { status: 503 },
      ),
    );

    render(<AdminOperationsPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("down");
    });
  });

  it("loads operation detail when operation_id is present in the URL", async () => {
    operationIdSearchParamMock.mockImplementation((key: string) =>
      key === "operation_id" ? "00000000-0000-0000-0000-000000000602" : null,
    );
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [],
            limit: 50,
            offset: 0,
            count: 0,
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            operation_id: "00000000-0000-0000-0000-000000000602",
            operation_type: "retry_ai_job",
            actor: "lyl",
            status: "failed",
            request_payload: { job_id: "job-1" },
            result_summary: {},
            error_message: "provider unavailable",
            related_resource_type: "ai_generation_job",
            related_resource_id: "job-1",
            started_at: "2026-06-20T12:00:00Z",
            finished_at: "2026-06-20T12:01:00Z",
            created_at: "2026-06-20T12:00:00Z",
            updated_at: "2026-06-20T12:01:00Z",
          }),
          { status: 200 },
        ),
      );

    render(<AdminOperationsPage />);

    expect(await screen.findByText("当前定位操作")).toBeInTheDocument();
    expect(screen.getByText("retry_ai_job")).toBeInTheDocument();
    expect(screen.getByText("provider unavailable")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/figure-chain/admin/operations/00000000-0000-0000-0000-000000000602",
    );
  });
});
