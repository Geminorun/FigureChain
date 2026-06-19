import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { usePersonDetail } from "@/hooks/use-person-detail";
import { usePersonEncounters } from "@/hooks/use-person-encounters";
import { useSourceRefDetail } from "@/hooks/use-source-ref-detail";
import { useSourceWorkDetail } from "@/hooks/use-source-work-detail";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const personDetail = {
  person_id: "person-1",
  display_name: "諸葛亮",
  primary_name_zh_hant: "諸葛亮",
  primary_name_zh_hans: "诸葛亮",
  primary_name_romanized: "Zhuge Liang",
  birth_year: 181,
  death_year: 234,
  index_year: 207,
  floruit_start_year: null,
  floruit_end_year: null,
  dynasty_code: 6,
  dynasty_label_zh: "三國",
  dynasty_label_en: "Three Kingdoms",
  is_female: false,
  notes: "蜀漢丞相",
  aliases: [],
  external_ids: [],
  encounter_summary: {
    active_count: 2,
    path_eligible_count: 1,
    high_certainty_count: 1,
  },
};

describe("person evidence hooks", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("usePersonDetail loads data and does not fetch without an id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(personDetail));
    vi.stubGlobal("fetch", fetchMock);

    const { result, rerender } = renderHook(
      ({ personId }: { personId: string | null }) => usePersonDetail(personId),
      { initialProps: { personId: null as string | null } },
    );

    expect(result.current.isLoading).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();

    rerender({ personId: "person-1" });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.detail?.display_name).toBe("諸葛亮");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/figure-chain/people/person-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("usePersonEncounters includes filters and supports refresh", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [],
        count: 0,
        limit: 20,
        offset: 0,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      usePersonEncounters("person-1", {
        status: "active",
        pathEligible: true,
        certaintyLevel: "high",
        encounterKind: "direct_interaction",
        limit: 20,
        offset: 0,
      }),
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/figure-chain/people/person-1/encounters?status=active&path_eligible=true&certainty_level=high&encounter_kind=direct_interaction&limit=20&offset=0",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    await act(async () => {
      result.current.refresh();
    });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });

  it("useSourceWorkDetail maps error responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "source_work_not_found",
              message: "source work was not found",
              details: {},
            },
          },
          404,
        ),
      ),
    );

    const { result } = renderHook(() => useSourceWorkDetail("999"));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error?.code).toBe("source_work_not_found");
  });

  it("useSourceRefDetail maps error responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "source_ref_not_found",
              message: "source ref was not found",
              details: {},
            },
          },
          404,
        ),
      ),
    );

    const { result } = renderHook(() => useSourceRefDetail("999"));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error?.code).toBe("source_ref_not_found");
  });
});
