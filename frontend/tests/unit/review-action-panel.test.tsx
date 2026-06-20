import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReviewActionPanel } from "@/components/review-action-panel";
import type { ReviewActionResponse, ReviewCandidateDetail } from "@/lib/figure-chain-types";
import { renderUi } from "@/test/render";

function makeDetail(defaultPromotable = true): ReviewCandidateDetail {
  return {
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
      default_promotable: defaultPromotable,
      default_path_eligible: defaultPromotable,
      reasons: defaultPromotable ? [] : ["not direct enough"],
    },
    linked_encounter: null,
    latest_ai_suggestion: null,
    ai_jobs: [],
  };
}

const actionResponse: ReviewActionResponse = {
  kind: "relationship",
  candidate_id: 960664,
  status: "promoted",
  reviewed_by: "lyl",
  encounter: null,
  message: null,
};

describe("ReviewActionPanel", () => {
  it("submits promote requests and refreshes after success", async () => {
    const onPromote = vi.fn().mockResolvedValue(actionResponse);
    const onActionComplete = vi.fn();

    renderUi(
      <ReviewActionPanel
        detail={makeDetail()}
        error={null}
        isSubmitting={false}
        onActionComplete={onActionComplete}
        onMarkNeedsReview={vi.fn()}
        onPromote={onPromote}
        onReject={vi.fn()}
      />,
    );

    await userEvent.type(screen.getByLabelText("reviewed_by"), "lyl");
    await userEvent.type(screen.getByLabelText("evidence summary"), "证据支持二人直接见面。");
    await userEvent.click(screen.getByRole("button", { name: "提升为 encounter" }));

    expect(onPromote).toHaveBeenCalledWith({
      reviewed_by: "lyl",
      evidence_summary: "证据支持二人直接见面。",
      note: null,
      allow_non_default: false,
    });
    expect(onActionComplete).toHaveBeenCalledWith(actionResponse);
  });

  it("disables default promote when candidate is not promotable", async () => {
    renderUi(
      <ReviewActionPanel
        detail={makeDetail(false)}
        error={null}
        isSubmitting={false}
        onActionComplete={vi.fn()}
        onMarkNeedsReview={vi.fn()}
        onPromote={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    await userEvent.type(screen.getByLabelText("reviewed_by"), "lyl");
    await userEvent.type(screen.getByLabelText("evidence summary"), "证据支持。");

    expect(screen.getByRole("button", { name: "提升为 encounter" })).toBeDisabled();
  });

  it("requires reject reason and submits reject requests", async () => {
    const onReject = vi.fn().mockResolvedValue({ ...actionResponse, status: "rejected" });
    renderUi(
      <ReviewActionPanel
        detail={makeDetail()}
        error={null}
        isSubmitting={false}
        onActionComplete={vi.fn()}
        onMarkNeedsReview={vi.fn()}
        onPromote={vi.fn()}
        onReject={onReject}
      />,
    );

    await userEvent.type(screen.getByLabelText("reviewed_by"), "lyl");
    expect(screen.getByRole("button", { name: "拒绝候选" })).toBeDisabled();

    await userEvent.type(screen.getByLabelText("reject reason"), "不是直接见面。");
    await userEvent.click(screen.getByRole("button", { name: "拒绝候选" }));

    expect(onReject).toHaveBeenCalledWith({
      reviewed_by: "lyl",
      reason: "不是直接见面。",
    });
  });

  it("submits needs-review requests and displays API errors", async () => {
    const onMarkNeedsReview = vi.fn().mockResolvedValue({
      ...actionResponse,
      status: "needs_review",
    });
    renderUi(
      <ReviewActionPanel
        detail={makeDetail()}
        error={{ code: "api_unavailable", message: "down", details: {} }}
        isSubmitting={false}
        onActionComplete={vi.fn()}
        onMarkNeedsReview={onMarkNeedsReview}
        onPromote={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("FigureChain API 不可用");

    await userEvent.type(screen.getByLabelText("reviewed_by"), "lyl");
    await userEvent.type(screen.getByLabelText("review note"), "需要补证。");
    await userEvent.click(screen.getByRole("button", { name: "标记待复核" }));

    expect(onMarkNeedsReview).toHaveBeenCalledWith({
      reviewed_by: "lyl",
      note: "需要补证。",
    });
  });

  it("submits linked encounter retractions and displays operation previews", async () => {
    const onRetractEncounter = vi.fn().mockResolvedValue({
      operation_id: "operation-1",
      operation_type: "retract_encounter",
      status: "succeeded",
      result: {
        encounter_id: "encounter-1",
        status: "retracted",
        path_eligible: false,
        linked_candidates_updated: 1,
      },
      preview: "已撤回 encounter-1",
    });

    renderUi(
      <ReviewActionPanel
        detail={{
          ...makeDetail(),
          linked_encounter: { encounter_id: "encounter-1", status: "active" },
        }}
        error={null}
        isSubmitting={false}
        onActionComplete={vi.fn()}
        onMarkNeedsReview={vi.fn()}
        onPromote={vi.fn()}
        onReject={vi.fn()}
        onRetractEncounter={onRetractEncounter}
      />,
    );

    await userEvent.type(screen.getByLabelText("reviewed_by"), "lyl");
    await userEvent.type(screen.getByLabelText("撤回原因"), "证据不足。");
    await userEvent.click(screen.getByRole("button", { name: "撤回 Encounter" }));

    expect(onRetractEncounter).toHaveBeenCalledWith("encounter-1", {
      reviewed_by: "lyl",
      note: "证据不足。",
      force: false,
    });
    expect(await screen.findByText(/操作已记录：operation-1/)).toBeInTheDocument();
    expect(screen.getByText("已撤回 encounter-1")).toBeInTheDocument();
  });
});
