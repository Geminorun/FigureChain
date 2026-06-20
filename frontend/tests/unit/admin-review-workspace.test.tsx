import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import AdminReviewPage from "../../app/admin/review/page";
import { renderUi } from "@/test/render";

const candidateSummary = {
  kind: "relationship",
  candidate_id: 960664,
  person_a: {
    person_id: "38966b03-8aa7-5143-8021-2d266889b6c5",
    cbdb_id: 780,
    display_name: "許幾",
    primary_name_zh_hant: "許幾",
    primary_name_zh_hans: "许几",
    primary_name_romanized: "Xu Ji",
    birth_year: 1054,
    death_year: 1115,
  },
  person_b: {
    person_id: "46cfdf66-08c4-5876-964b-4a95d098afe9",
    cbdb_id: 630,
    display_name: "韓琦",
    primary_name_zh_hant: "韓琦",
    primary_name_zh_hans: "韩琦",
    primary_name_romanized: "Han Qi",
    birth_year: 1008,
    death_year: 1075,
  },
  relation_type: "visited",
  time_summary: "北宋",
  place_summary: "魏",
  status: "promoted",
  confidence: 0.92,
  evidence_count: 1,
  source_count: 1,
  promotion_readiness: {
    default_promotable: true,
    default_path_eligible: true,
    reasons: [],
  },
  latest_ai_job_status: null,
  has_ai_suggestion: false,
};

const candidateDetail = {
  ...candidateSummary,
  relation: {
    relation_type: "visited",
    basis: "source_ref",
    strength: "high",
    notes: null,
    source_name: "CBDB",
    source_table: "assoc_data",
    source_pk: "960664",
  },
  time: { summary: "北宋", pages: "11905" },
  place: { summary: "魏" },
  source_refs: [],
  evidence: [],
  linked_encounter: {
    encounter_id: "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
    status: "active",
  },
  latest_ai_suggestion: null,
  ai_jobs: [],
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("AdminReviewWorkspace", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads candidates from admin APIs and retracts linked encounters", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith("/api/figure-chain/admin/review/candidates?")) {
        return Promise.resolve(
          jsonResponse({ items: [candidateSummary], limit: 20, offset: 0, count: 1 }),
        );
      }
      if (url === "/api/figure-chain/admin/review/candidates/relationship/960664") {
        return Promise.resolve(jsonResponse(candidateDetail));
      }
      if (url.startsWith("/api/figure-chain/ai/jobs?")) {
        return Promise.resolve(jsonResponse({ items: [], count: 0, limit: 20 }));
      }
      if (
        url ===
        "/api/figure-chain/admin/review/encounters/e4f22ec2-22f7-4cda-bcc1-73aa83d0685f/retract"
      ) {
        return Promise.resolve(
          jsonResponse({
            operation_id: "operation-1",
            operation_type: "retract_encounter",
            status: "succeeded",
            result: {
              encounter_id: "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
              status: "retracted",
              path_eligible: false,
              linked_candidates_updated: 1,
            },
            preview: "已撤回 Encounter",
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({ error: { code: "not_found", message: `${url}:${init?.method}`, details: {} } }, 404),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderUi(<AdminReviewPage />);

    await waitFor(() => expect(screen.getByText(/許幾/)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /relationship 960664/ }));

    await waitFor(() => expect(screen.getByText(/当前候选已关联 Encounter/)).toBeInTheDocument());
    await userEvent.type(screen.getByLabelText("reviewed_by"), "local");
    await userEvent.type(screen.getByLabelText("撤回原因"), "误判");
    await userEvent.click(screen.getByRole("button", { name: "撤回 Encounter" }));

    await waitFor(() => expect(screen.getByText(/操作已记录：operation-1/)).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/figure-chain/admin/review/encounters/e4f22ec2-22f7-4cda-bcc1-73aa83d0685f/retract",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          reviewed_by: "local",
          note: "误判",
          force: false,
        }),
      }),
    );
  });
});
