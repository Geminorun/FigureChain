import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MultiPathResult } from "@/components/multipath-result";
import type { MultiPathChainResponse } from "@/lib/figure-chain-types";
import { renderUi } from "@/test/render";

const result: MultiPathChainResponse = {
  status: "found",
  source_person_id: "source",
  target_person_id: "target",
  max_depth: 12,
  max_paths: 5,
  extra_depth: 1,
  shortest_length: 1,
  returned_paths: 1,
  filters_applied: {
    min_certainty_level: "high",
    encounter_kinds: [],
    exclude_person_ids: [],
    exclude_encounter_ids: [],
    source_work_ids: [],
    intermediate_dynasty_codes: [],
    intermediate_year_min: null,
    intermediate_year_max: null,
  },
  paths: [
    {
      path_id: "path-1",
      rank: 1,
      chain_hash: "sha256:test",
      length: 1,
      quality_score: 1,
      people: [
        {
          person_id: "source",
          display_name: "许几",
          birth_year: null,
          death_year: null,
          cbdb_external_id: null,
        },
        {
          person_id: "target",
          display_name: "韩琦",
          birth_year: null,
          death_year: null,
          cbdb_external_id: null,
        },
      ],
      edges: [
        {
          encounter_id: "encounter-1",
          encounter_kind: "direct_interaction",
          certainty_level: "high",
          pages: null,
          evidence_summary: "见面",
        },
      ],
    },
  ],
};

describe("MultiPathResult", () => {
  it("renders path list and selects encounter", async () => {
    const onSelectEncounter = vi.fn();

    renderUi(
      <MultiPathResult
        error={null}
        isLoading={false}
        result={result}
        onSelectEncounter={onSelectEncounter}
      />,
    );

    expect(screen.getByText("找到 1 条路径")).toBeInTheDocument();
    expect(screen.getByText(/长度 1 \/ 评分 1.00/)).toBeInTheDocument();
    expect(screen.getByText("直接接触 · 高可信度")).toBeInTheDocument();
    expect(screen.getByText(/接触记录 ID/)).toBeInTheDocument();
    expect(screen.queryByText("direct_interaction")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /path-1/ }));
    await userEvent.click(screen.getByRole("button", { name: /查看证据/ }));

    expect(onSelectEncounter).toHaveBeenCalledWith("encounter-1");
  });
});
