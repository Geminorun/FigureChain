import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChainResult } from "@/components/chain-result";
import { shortestChainFound, shortestChainNoPath } from "@/test/fixtures";
import { renderUi } from "@/test/render";

describe("ChainResult", () => {
  it("renders found path and evidence action", async () => {
    const user = userEvent.setup();
    const onSelectEncounter = vi.fn();

    renderUi(
      <ChainResult
        error={null}
        isLoading={false}
        result={shortestChainFound}
        onSelectEncounter={onSelectEncounter}
      />,
    );

    expect(screen.getByText("路径长度：1")).toBeInTheDocument();
    expect(screen.getByText("許幾")).toBeInTheDocument();
    expect(screen.getByText("韓琦")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /查看证据/ }));
    expect(onSelectEncounter).toHaveBeenCalledWith(
      "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
    );
  });

  it("renders no path state", () => {
    renderUi(
      <ChainResult
        error={null}
        isLoading={false}
        result={shortestChainNoPath}
        onSelectEncounter={vi.fn()}
      />,
    );

    expect(screen.getByText("暂未找到路径")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    renderUi(
      <ChainResult
        error={null}
        isLoading
        result={null}
        onSelectEncounter={vi.fn()}
      />,
    );

    expect(screen.getByText("查链中...")).toBeInTheDocument();
  });
});
