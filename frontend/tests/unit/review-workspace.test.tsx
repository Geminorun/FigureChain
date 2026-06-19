import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReviewPage from "../../app/review/page";
import { ReviewWorkspace } from "@/components/review-workspace";
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
  status: "needs_review",
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
  source_refs: [
    {
      source_ref_id: 3853784,
      source_work_id: 7596,
      title_zh: "宋史",
      title_en: null,
      pages: "11905",
      notes: "字先之，贵溪人，以诸生谒韩琦于魏。",
    },
  ],
  evidence: [
    {
      evidence_id: 1,
      source_ref_id: 3853784,
      evidence_kind: "source_ref",
      evidence_summary: "许几谒韩琦于魏",
      pages: "11905",
    },
  ],
  linked_encounter: null,
  latest_ai_suggestion: null,
  ai_jobs: [],
};

const queuedAiJob = {
  id: "9d6958d5-c0e5-4112-9659-bb47c27cbdb7",
  job_type: "candidate_review_suggestion",
  target_type: "candidate",
  target_kind: "relationship",
  target_id: 960664,
  status: "queued",
  created_by: "lyl",
  params: {},
  result_ref_type: null,
  result_ref_id: null,
  error_code: null,
  error_message: null,
  queue_backend: "rq",
  queue_name: "figure-ai",
  queue_job_id: "rq-job-501",
  enqueued_at: "2026-06-19T00:00:01Z",
  attempt_count: 1,
  max_attempts: 3,
  next_run_at: null,
  cancel_requested_at: null,
  worker_id: "worker-1",
  heartbeat_at: "2026-06-19T00:00:02Z",
  started_at: null,
  finished_at: null,
  created_at: "2026-06-18T00:00:00Z",
  updated_at: "2026-06-18T00:00:00Z",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("ReviewWorkspace", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads candidates and selects a candidate detail", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith("/api/figure-chain/review/candidates?")) {
        return Promise.resolve(
          jsonResponse({ items: [candidateSummary], limit: 20, offset: 0, count: 1 }),
        );
      }
      if (url === "/api/figure-chain/review/candidates/relationship/960664") {
        return Promise.resolve(jsonResponse(candidateDetail));
      }
      if (url.startsWith("/api/figure-chain/ai/jobs?")) {
        return Promise.resolve(jsonResponse({ items: [queuedAiJob], count: 1, limit: 20 }));
      }
      return Promise.resolve(jsonResponse({ error: { code: "not_found", message: url, details: {} } }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderUi(<ReviewWorkspace />);

    await waitFor(() => expect(screen.getByText(/許幾/)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /relationship 960664/ }));

    await waitFor(() => expect(screen.getByText("宋史")).toBeInTheDocument());
    expect(screen.getByText("审核动作")).toBeInTheDocument();
    expect(screen.getByText("AI 建议")).toBeInTheDocument();
    expect(screen.getByText(/queue rq/)).toBeInTheDocument();
  });

  it("renders the review page", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ items: [], limit: 20, offset: 0, count: 0 }),
      ),
    );

    renderUi(<ReviewPage />);

    expect(screen.getByRole("heading", { name: "候选审核工作台" })).toBeInTheDocument();
  });
});
