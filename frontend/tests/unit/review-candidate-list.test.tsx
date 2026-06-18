import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReviewCandidateList } from "@/components/review-candidate-list";
import type { ReviewCandidateListResponse } from "@/lib/figure-chain-types";
import { renderUi } from "@/test/render";

const response: ReviewCandidateListResponse = {
  limit: 20,
  offset: 0,
  count: 1,
  items: [
    {
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
      latest_ai_job_status: "succeeded",
      has_ai_suggestion: true,
    },
  ],
};

describe("ReviewCandidateList", () => {
  it("renders candidates and selects one", async () => {
    const onSelect = vi.fn();
    renderUi(
      <ReviewCandidateList
        data={response}
        error={null}
        filters={{ kind: "relationship", status: "needs_review", limit: 20, offset: 0 }}
        isLoading={false}
        selectedCandidateKey={null}
        onFiltersChange={vi.fn()}
        onRefresh={vi.fn()}
        onSelectCandidate={onSelect}
      />,
    );

    expect(screen.getByText(/許幾/)).toBeInTheDocument();
    expect(screen.getByText(/韓琦/)).toBeInTheDocument();
    expect(screen.getByText(/confidence 0.92/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /relationship 960664/ }));

    expect(onSelect).toHaveBeenCalledWith({ kind: "relationship", candidateId: 960664 });
  });

  it("submits filters", async () => {
    const onFiltersChange = vi.fn();
    renderUi(
      <ReviewCandidateList
        data={response}
        error={null}
        filters={{ limit: 20, offset: 0 }}
        isLoading={false}
        selectedCandidateKey={null}
        onFiltersChange={onFiltersChange}
        onRefresh={vi.fn()}
        onSelectCandidate={vi.fn()}
      />,
    );

    await userEvent.selectOptions(screen.getByLabelText("kind"), "relationship");
    await userEvent.selectOptions(screen.getByLabelText("status"), "needs_review");
    await userEvent.clear(screen.getByLabelText("min confidence"));
    await userEvent.type(screen.getByLabelText("min confidence"), "0.8");
    await userEvent.type(screen.getByLabelText("person id"), "38966b03-8aa7-5143-8021-2d266889b6c5");
    await userEvent.click(screen.getByRole("button", { name: "应用筛选" }));

    expect(onFiltersChange).toHaveBeenCalledWith({
      kind: "relationship",
      status: "needs_review",
      minConfidence: 0.8,
      personId: "38966b03-8aa7-5143-8021-2d266889b6c5",
      limit: 20,
      offset: 0,
    });
  });

  it("renders loading, empty, and error states", () => {
    const { rerender } = renderUi(
      <ReviewCandidateList
        data={null}
        error={null}
        filters={{ limit: 20, offset: 0 }}
        isLoading={true}
        selectedCandidateKey={null}
        onFiltersChange={vi.fn()}
        onRefresh={vi.fn()}
        onSelectCandidate={vi.fn()}
      />,
    );
    expect(screen.getByText("正在加载候选记录...")).toBeInTheDocument();

    rerender(
      <ReviewCandidateList
        data={{ items: [], limit: 20, offset: 0, count: 0 }}
        error={null}
        filters={{ limit: 20, offset: 0 }}
        isLoading={false}
        selectedCandidateKey={null}
        onFiltersChange={vi.fn()}
        onRefresh={vi.fn()}
        onSelectCandidate={vi.fn()}
      />,
    );
    expect(screen.getByText("没有候选记录")).toBeInTheDocument();

    rerender(
      <ReviewCandidateList
        data={null}
        error={{ code: "api_unavailable", message: "down", details: {} }}
        filters={{ limit: 20, offset: 0 }}
        isLoading={false}
        selectedCandidateKey={null}
        onFiltersChange={vi.fn()}
        onRefresh={vi.fn()}
        onSelectCandidate={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("FigureChain API 不可用");
  });
});
