import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChainExplanationPanel } from "@/components/chain-explanation-panel";
import type { AIChainExplanation } from "@/lib/figure-chain-types";
import { renderUi } from "@/test/render";

const explanation: AIChainExplanation = {
  id: "00000000-0000-0000-0000-000000000401",
  ai_run_id: "00000000-0000-0000-0000-000000000301",
  chain_hash: "known-chain-hash",
  source_person_id: "38966b03-8aa7-5143-8021-2d266889b6c5",
  target_person_id: "46cfdf66-08c4-5876-964b-4a95d098afe9",
  max_depth: 12,
  encounter_ids: ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
  language: "zh-Hans",
  summary: "这条人物链由一条已审核 encounter 组成。",
  edge_explanations: [
    {
      encounter_id: "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
      explanation: "许几谒见韩琦。",
      evidence_basis: "encounter_evidence",
      source_ref_ids: [3853784],
    },
  ],
  source_ref_ids: [3853784],
  status: "generated",
  created_at: "2026-06-13T00:00:00Z",
};

describe("ChainExplanationPanel", () => {
  it("renders stored summary and edge explanations", () => {
    renderUi(
      <ChainExplanationPanel
        explanation={explanation}
        isLoading={false}
        unavailableMessage={null}
      />,
    );

    expect(screen.getByText("AI 解释")).toBeInTheDocument();
    expect(screen.getByText("这条人物链由一条已审核 encounter 组成。")).toBeInTheDocument();
    expect(screen.getByText("许几谒见韩琦。")).toBeInTheDocument();
  });

  it("renders unavailable message without hiding the result area", () => {
    renderUi(
      <ChainExplanationPanel
        explanation={null}
        isLoading={false}
        unavailableMessage="这条路径暂时还没有生成 AI 解释。"
      />,
    );

    expect(screen.getByText("这条路径暂时还没有生成 AI 解释。")).toBeInTheDocument();
  });
});
