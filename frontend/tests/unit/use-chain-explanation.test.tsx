import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useChainExplanation } from "@/hooks/use-chain-explanation";

describe("useChainExplanation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not fetch when chain hash is null", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useChainExplanation(null));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.explanation).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it("loads an explanation for a chain hash", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            id: "00000000-0000-0000-0000-000000000401",
            ai_run_id: "00000000-0000-0000-0000-000000000301",
            chain_hash: "known-chain-hash",
            source_person_id: "38966b03-8aa7-5143-8021-2d266889b6c5",
            target_person_id: "46cfdf66-08c4-5876-964b-4a95d098afe9",
            max_depth: 12,
            encounter_ids: ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
            language: "zh-Hans",
            summary: "这条人物链由一条已审核 encounter 组成。",
            edge_explanations: [],
            source_ref_ids: [],
            status: "generated",
            created_at: "2026-06-13T00:00:00Z",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      ),
    );

    const { result } = renderHook(() => useChainExplanation("known-chain-hash"));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.explanation?.chain_hash).toBe("known-chain-hash");
    expect(result.current.error).toBeNull();
  });
});
