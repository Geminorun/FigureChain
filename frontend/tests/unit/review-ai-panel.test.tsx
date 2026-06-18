import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReviewAiPanel } from "@/components/review-ai-panel";
import type {
  AiJobResponse,
  ReviewCandidateDetail,
} from "@/lib/figure-chain-types";
import { renderUi } from "@/test/render";

const detail: ReviewCandidateDetail = {
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
  relation: {
    relation_type: "visited",
    basis: "source_ref",
    strength: "high",
    notes: null,
    source_name: "CBDB",
    source_table: "assoc_data",
    source_pk: "960664",
  },
  time: null,
  place: null,
  status: "needs_review",
  confidence: 0.92,
  source_refs: [],
  evidence: [],
  promotion_readiness: {
    default_promotable: true,
    default_path_eligible: true,
    reasons: [],
  },
  linked_encounter: null,
  latest_ai_suggestion: {
    suggestion_id: "6d027955-5a03-42a0-8425-f76b82073ebf",
    ai_run_id: "9d6958d5-c0e5-4112-9659-bb47c27cbdb7",
    status: "generated",
    recommendation: "promote",
    summary: "证据支持二人直接见面。".repeat(20),
    created_at: "2026-06-18T00:00:00Z",
  },
  ai_jobs: [
    {
      run_id: "9d6958d5-c0e5-4112-9659-bb47c27cbdb7",
      status: "succeeded",
      purpose: "candidate_review_suggestion",
      created_at: "2026-06-18T00:00:00Z",
      finished_at: "2026-06-18T00:00:10Z",
    },
  ],
};

const queuedJob: AiJobResponse = {
  id: "9d6958d5-c0e5-4112-9659-bb47c27cbdb7",
  job_type: "candidate_review_suggestion",
  target_type: "review_candidate",
  target_kind: "relationship",
  target_id: 960664,
  status: "queued",
  created_by: "lyl",
  params: {},
  result_ref_type: null,
  result_ref_id: null,
  error_code: null,
  error_message: null,
  started_at: null,
  finished_at: null,
  created_at: "2026-06-18T00:00:00Z",
  updated_at: "2026-06-18T00:00:00Z",
};

describe("ReviewAiPanel", () => {
  it("renders latest AI suggestion and job history", () => {
    renderUi(
      <ReviewAiPanel
        activeJob={queuedJob}
        detail={detail}
        error={null}
        isCreating={false}
        jobs={[queuedJob]}
        onCreateJob={vi.fn()}
        onRefreshCandidate={vi.fn()}
      />,
    );

    expect(screen.getByText("AI 建议")).toBeInTheDocument();
    expect(screen.getByText(/recommendation/)).toHaveTextContent("promote");
    expect(screen.getByText("AI worker 已排队或执行中，结果生成后会刷新详情。")).toBeInTheDocument();
    expect(screen.getByText(/queued/)).toBeInTheDocument();
  });

  it("creates a new AI job with created_by", async () => {
    const onCreateJob = vi.fn().mockResolvedValue(queuedJob);
    renderUi(
      <ReviewAiPanel
        activeJob={null}
        detail={detail}
        error={null}
        isCreating={false}
        jobs={[]}
        onCreateJob={onCreateJob}
        onRefreshCandidate={vi.fn()}
      />,
    );

    await userEvent.type(screen.getByLabelText("created_by"), "lyl");
    await userEvent.click(screen.getByRole("button", { name: "生成 AI 建议" }));

    expect(onCreateJob).toHaveBeenCalledWith({ createdBy: "lyl" });
  });

  it("refreshes candidate detail when an active job succeeds", async () => {
    const onRefreshCandidate = vi.fn();
    renderUi(
      <ReviewAiPanel
        activeJob={{ ...queuedJob, status: "succeeded" }}
        detail={detail}
        error={null}
        isCreating={false}
        jobs={[{ ...queuedJob, status: "succeeded" }]}
        onCreateJob={vi.fn()}
        onRefreshCandidate={onRefreshCandidate}
      />,
    );

    await waitFor(() => expect(onRefreshCandidate).toHaveBeenCalledTimes(1));
  });

  it("renders disabled and failure states", () => {
    renderUi(
      <ReviewAiPanel
        activeJob={{ ...queuedJob, status: "failed", error_message: "provider unavailable" }}
        detail={null}
        error={{ code: "api_unavailable", message: "down", details: {} }}
        isCreating={false}
        jobs={[]}
        onCreateJob={vi.fn()}
        onRefreshCandidate={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "生成 AI 建议" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("FigureChain API 不可用");
    expect(screen.getByText(/provider unavailable/)).toBeInTheDocument();
  });
});
