import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PersonDetailPage } from "@/components/person-detail-page";
import { PersonEncounterList } from "@/components/person-encounter-list";
import { renderUi } from "@/test/render";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const personId = "00000000-0000-0000-0000-000000000001";
const encounterId = "00000000-0000-0000-0000-000000000101";

const personDetail = {
  person_id: personId,
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
  aliases: [
    {
      alias_zh_hant: "孔明",
      alias_zh_hans: "孔明",
      alias_romanized: null,
      alias_type_label_zh: "字",
      alias_type_label_en: "courtesy name",
    },
  ],
  external_ids: [{ source_name: "CBDB", external_id: "25403" }],
  encounter_summary: {
    active_count: 2,
    path_eligible_count: 1,
    high_certainty_count: 1,
  },
};

const encounterList = {
  items: [
    {
      encounter_id: encounterId,
      other_person_id: "00000000-0000-0000-0000-000000000002",
      other_person_name: "司馬懿",
      other_person_birth_year: 179,
      other_person_death_year: 251,
      encounter_kind: "direct_interaction",
      certainty_level: "high",
      path_eligible: true,
      source_work_id: 1,
      source_title: "三國志",
      pages: "12a",
      evidence_summary: "有直接交往證據",
      status: "active",
      reviewed_by: "lyl",
      reviewed_at: "2026-06-19T00:00:00Z",
    },
  ],
  count: 1,
  limit: 50,
  offset: 0,
};

describe("person detail pages", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders person profile, aliases, external ids and encounter counts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/encounters")) {
          return Promise.resolve(jsonResponse(encounterList));
        }
        return Promise.resolve(jsonResponse(personDetail));
      }),
    );

    renderUi(<PersonDetailPage personId={personId} />);

    await screen.findByRole("heading", { name: "諸葛亮" });
    expect(screen.getByText("Three Kingdoms")).toBeInTheDocument();
    expect(screen.getByText("孔明")).toBeInTheDocument();
    expect(screen.getByText(/CBDB/)).toBeInTheDocument();
    expect(screen.getByText(/25403/)).toBeInTheDocument();
    expect(screen.getByText(/active 2/)).toBeInTheDocument();
    expect(screen.getByText(/path eligible 1/)).toBeInTheDocument();
    expect(screen.getByText(/high certainty 1/)).toBeInTheDocument();
  });

  it("renders encounter links in the person encounter list", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(encounterList)));

    renderUi(<PersonEncounterList personId={personId} />);

    const encounterLink = await screen.findByRole("link", { name: encounterId });
    expect(encounterLink).toHaveAttribute("href", `/encounters/${encounterId}`);
    expect(screen.getByRole("link", { name: "司馬懿" })).toHaveAttribute(
      "href",
      "/people/00000000-0000-0000-0000-000000000002",
    );
  });

  it("renders empty and error states without layout-only crashes", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ items: [], count: 0, limit: 50, offset: 0 }))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "person_not_found",
              message: "person was not found",
              details: {},
            },
          },
          404,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = renderUi(<PersonEncounterList personId={personId} />);

    await screen.findByText("没有已审核 Encounter");
    rerender(<PersonDetailPage personId={personId} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
