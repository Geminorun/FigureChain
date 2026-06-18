import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useMultiPathChain } from "@/hooks/use-multipath-chain";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("useMultiPathChain", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts multipath requests and stores result", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        status: "no_path",
        source_person_id: "source",
        target_person_id: "target",
        max_depth: 12,
        max_paths: 5,
        extra_depth: 0,
        shortest_length: null,
        returned_paths: 0,
        paths: [],
        filters_applied: {
          min_certainty_level: "high",
          encounter_kinds: [],
          exclude_person_ids: [],
          exclude_encounter_ids: [],
          source_work_ids: [],
          intermediate_dynasty_codes: [],
          intermediate_year_min: null,
          intermediate_year_max: null,
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useMultiPathChain());

    await act(async () => {
      await result.current.findMultiPath({
        source: { person_id: "source" },
        target: { person_id: "target" },
        max_depth: 12,
        max_paths: 5,
        extra_depth: 0,
        filters: {
          min_certainty_level: "high",
          encounter_kinds: [],
          exclude_person_ids: [],
          exclude_encounter_ids: [],
          source_work_ids: [],
          intermediate_dynasty_codes: [],
          intermediate_year_min: null,
          intermediate_year_max: null,
        },
      });
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.result?.status).toBe("no_path");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/figure-chain/chains/multipath",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
