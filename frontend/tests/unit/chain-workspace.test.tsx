import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChainWorkspace } from "@/components/chain-workspace";
import { renderUi } from "@/test/render";

describe("ChainWorkspace", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders dependency details from not_ready readiness responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: "not_ready",
            dependencies: {
              postgresql: { status: "ok" },
              neo4j: { status: "error", message: "bolt down" },
            },
          }),
          {
            status: 503,
            headers: { "content-type": "application/json" },
          },
        ),
      ),
    );

    renderUi(<ChainWorkspace />);

    await waitFor(() => {
      expect(screen.getByText("部分依赖不可用")).toBeInTheDocument();
    });
    expect(screen.getByText("neo4j: bolt down")).toBeInTheDocument();
    expect(screen.getByLabelText("max_paths")).toBeInTheDocument();
    expect(screen.getByLabelText("extra_depth")).toBeInTheDocument();
    expect(screen.getByLabelText("min_certainty_level")).toBeInTheDocument();
    expect(
      screen.queryByText("FigureChain API readiness 暂不可用。"),
    ).not.toBeInTheDocument();
  });
});
