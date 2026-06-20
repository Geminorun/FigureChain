import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminOperationsPage } from "@/components/admin-operations-page";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  global.fetch = fetchMock;
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
});
