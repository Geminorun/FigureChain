import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PersonSelector } from "@/components/person-selector";
import { xuJi } from "@/test/fixtures";
import { renderUi } from "@/test/render";

describe("PersonSelector", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("searches and selects a person", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ query: "許幾", limit: 10, items: [xuJi] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    renderUi(
      <PersonSelector
        label="起点人物"
        selectedPerson={null}
        onSelect={onSelect}
      />,
    );

    await user.type(screen.getByLabelText("起点人物"), "許幾");
    await waitFor(() => expect(screen.getByText("Xu Ji")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /选择 許幾/ }));

    expect(onSelect).toHaveBeenCalledWith(xuJi);
  });

  it("clears selected person", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    renderUi(
      <PersonSelector
        label="起点人物"
        selectedPerson={xuJi}
        onSelect={onSelect}
      />,
    );

    await user.click(screen.getByRole("button", { name: "清除起点人物" }));

    expect(onSelect).toHaveBeenCalledWith(null);
  });
});
