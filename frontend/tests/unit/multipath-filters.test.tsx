import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MultiPathFiltersPanel } from "@/components/multipath-filters";
import { renderUi } from "@/test/render";

describe("MultiPathFiltersPanel", () => {
  it("edits max paths and certainty filter", async () => {
    const onChange = vi.fn();

    renderUi(
      <MultiPathFiltersPanel
        value={{
          maxPaths: 5,
          extraDepth: 0,
          minCertaintyLevel: "high",
          encounterKinds: [],
        }}
        onChange={onChange}
      />,
    );

    await userEvent.clear(screen.getByLabelText("max_paths"));
    await userEvent.type(screen.getByLabelText("max_paths"), "8");
    await userEvent.selectOptions(
      screen.getByLabelText("min_certainty_level"),
      "medium",
    );

    expect(onChange).toHaveBeenCalled();
  });
});
