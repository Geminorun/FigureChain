import { describe, expect, it } from "vitest";

import type {
  MultiPathChainRequest,
  MultiPathChainResponse,
} from "@/lib/figure-chain-types";

describe("multipath frontend types", () => {
  it("supports multipath request and response shapes", () => {
    const request: MultiPathChainRequest = {
      source: { person_id: "source" },
      target: { person_id: "target" },
      max_depth: 12,
      max_paths: 5,
      extra_depth: 1,
      filters: {
        min_certainty_level: "high",
        encounter_kinds: ["direct_interaction"],
        exclude_person_ids: [],
        exclude_encounter_ids: [],
        source_work_ids: [],
        intermediate_dynasty_codes: [],
        intermediate_year_min: null,
        intermediate_year_max: null,
      },
    };
    const response: MultiPathChainResponse = {
      status: "no_path",
      source_person_id: "source",
      target_person_id: "target",
      max_depth: 12,
      max_paths: 5,
      extra_depth: 1,
      shortest_length: null,
      returned_paths: 0,
      paths: [],
      filters_applied: request.filters,
    };

    expect(response.status).toBe("no_path");
    expect(request.filters.min_certainty_level).toBe("high");
  });
});
