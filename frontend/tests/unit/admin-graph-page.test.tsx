import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminGraphPage } from "@/components/admin-graph-page";
import { renderUi } from "@/test/render";

const fetchMock = vi.fn();

const statusResponse = {
  latest_success: {
    id: "batch-success",
    mode: "rebuild",
    status: "succeeded",
    triggered_by: "local",
    source_watermark: null,
    encounters_seen: 10,
    relationships_written: 10,
    relationships_deleted: 0,
    persons_written: 12,
    validation_status: "passed",
    validation_summary: { "graph:relationship_count": "postgres=10 neo4j=10" },
    error_code: null,
    error_message: null,
    started_at: "2026-06-20T12:00:00Z",
    finished_at: "2026-06-20T12:01:00Z",
  },
  latest_failed: {
    id: "batch-failed",
    mode: "incremental",
    status: "failed",
    triggered_by: "local",
    source_watermark: null,
    encounters_seen: 2,
    relationships_written: 0,
    relationships_deleted: 0,
    persons_written: 0,
    validation_status: "not_run",
    validation_summary: {},
    error_code: "graph_projection_failed",
    error_message: "Neo4j unavailable",
    started_at: "2026-06-20T11:00:00Z",
    finished_at: "2026-06-20T11:01:00Z",
  },
  active_encounter_count: 20,
  path_eligible_encounter_count: 15,
  stale_running_operations: [
    {
      operation_id: "00000000-0000-0000-0000-000000000701",
      operation_type: "sync_graph_rebuild",
      actor: "local",
      status: "running",
      request_payload: {},
      result_summary: {},
      error_message: null,
      related_resource_type: "graph_projection_batch",
      related_resource_id: null,
      started_at: "2026-06-20T10:00:00Z",
      finished_at: null,
      created_at: "2026-06-20T10:00:00Z",
      updated_at: "2026-06-20T10:00:00Z",
    },
  ],
};

describe("AdminGraphPage", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/figure-chain/admin/graph/status") {
        return Promise.resolve(jsonResponse(statusResponse));
      }
      return Promise.resolve(
        jsonResponse({
          operation_id: "00000000-0000-0000-0000-000000000702",
          operation_type: "validate_encounters",
          status: "queued",
          preview: "figure-data validate-encounters",
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  it("renders graph status, batches, actions, and stale operation links", async () => {
    renderUi(<AdminGraphPage />);

    expect(await screen.findByText("20")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("batch-success")).toBeInTheDocument();
    expect(screen.getByText("batch-failed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "校验 Encounter" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "全量重建同步" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "增量同步" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "校验图投影" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: "00000000-0000-0000-0000-000000000701",
      }),
    ).toHaveAttribute(
      "href",
      "/admin/operations?operation_id=00000000-0000-0000-0000-000000000701",
    );
  });

  it("shows returned operation id and preview after an action", async () => {
    renderUi(<AdminGraphPage />);

    await screen.findByText("batch-success");
    await userEvent.click(screen.getByRole("button", { name: "校验 Encounter" }));

    await waitFor(() => {
      expect(
        screen.getByText("00000000-0000-0000-0000-000000000702"),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("figure-data validate-encounters")).toBeInTheDocument();
  });
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
