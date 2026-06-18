import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReviewCandidateDetail } from "@/components/review-candidate-detail";
import type { ReviewCandidateDetail as ReviewCandidateDetailType } from "@/lib/figure-chain-types";
import { renderUi } from "@/test/render";

const detail: ReviewCandidateDetailType = {
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
    notes: "direct visit",
    source_name: "CBDB",
    source_table: "assoc_data",
    source_pk: "960664",
  },
  time: { summary: "北宋", pages: "11905" },
  place: { summary: "魏" },
  status: "needs_review",
  confidence: 0.92,
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
  promotion_readiness: {
    default_promotable: true,
    default_path_eligible: true,
    reasons: ["high confidence direct interaction"],
  },
  linked_encounter: {
    encounter_id: "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
    status: "active",
  },
  latest_ai_suggestion: null,
  ai_jobs: [],
};

describe("ReviewCandidateDetail", () => {
  it("renders candidate detail sections", () => {
    renderUi(<ReviewCandidateDetail detail={detail} error={null} isLoading={false} />);

    expect(screen.getByText("relationship 960664")).toBeInTheDocument();
    expect(screen.getByText("許幾")).toBeInTheDocument();
    expect(screen.getByText("韓琦")).toBeInTheDocument();
    expect(screen.getByText("visited")).toBeInTheDocument();
    expect(screen.getByText("北宋")).toBeInTheDocument();
    expect(screen.getByText("魏")).toBeInTheDocument();
    expect(screen.getByText("宋史")).toBeInTheDocument();
    expect(screen.getByText("许几谒韩琦于魏")).toBeInTheDocument();
    expect(screen.getAllByText("yes")).toHaveLength(2);
    expect(screen.getByText(/active/)).toBeInTheDocument();
  });

  it("renders empty, loading, and error states", () => {
    const { rerender } = renderUi(
      <ReviewCandidateDetail detail={null} error={null} isLoading={false} />,
    );
    expect(screen.getByText("请选择候选记录")).toBeInTheDocument();

    rerender(<ReviewCandidateDetail detail={null} error={null} isLoading={true} />);
    expect(screen.getByText("正在加载候选详情...")).toBeInTheDocument();

    rerender(
      <ReviewCandidateDetail
        detail={null}
        error={{ code: "api_unavailable", message: "down", details: {} }}
        isLoading={false}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("FigureChain API 不可用");
  });
});
