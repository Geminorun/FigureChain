import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  MultiPathFiltersPanel,
  type MultiPathFilterState,
} from "@/components/multipath-filters";
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
          excludePersonIds: [],
          excludeEncounterIds: [],
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

  it("edits excluded person and encounter ids", async () => {
    const onChange = vi.fn();
    function StatefulPanel() {
      const [value, setValue] = useState<MultiPathFilterState>({
        maxPaths: 5,
        extraDepth: 0,
        minCertaintyLevel: "high",
        encounterKinds: [],
        excludePersonIds: [],
        excludeEncounterIds: [],
      });
      return (
        <MultiPathFiltersPanel
          value={value}
          onChange={(next) => {
            setValue(next);
            onChange(next);
          }}
        />
      );
    }

    renderUi(<StatefulPanel />);

    await userEvent.type(
      screen.getByLabelText("exclude_person_ids"),
      "38966b03-8aa7-5143-8021-2d266889b6c5",
    );
    await userEvent.type(
      screen.getByLabelText("exclude_encounter_ids"),
      "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
    );

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        excludePersonIds: ["38966b03-8aa7-5143-8021-2d266889b6c5"],
      }),
    );
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        excludeEncounterIds: ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
      }),
    );
  });

  it("keeps typed separators while editing excluded ids", async () => {
    function StatefulPanel() {
      const [value, setValue] = useState<MultiPathFilterState>({
        maxPaths: 5,
        extraDepth: 0,
        minCertaintyLevel: "high",
        encounterKinds: [],
        excludePersonIds: [],
        excludeEncounterIds: [],
      });
      return <MultiPathFiltersPanel value={value} onChange={setValue} />;
    }

    renderUi(<StatefulPanel />);

    const firstId = "38966b03-8aa7-5143-8021-2d266889b6c5";
    const secondId = "46cfdf66-08c4-5876-964b-4a95d098afe9";
    const textarea = screen.getByLabelText("exclude_person_ids");

    await userEvent.type(textarea, `${firstId}{enter}${secondId}`);

    expect(textarea).toHaveValue(`${firstId}\n${secondId}`);
  });
});
