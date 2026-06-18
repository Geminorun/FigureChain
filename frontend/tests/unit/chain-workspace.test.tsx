import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChainWorkspace } from "@/components/chain-workspace";
import { hanQi, readyResponse, xuJi } from "@/test/fixtures";
import { renderUi } from "@/test/render";

describe("ChainWorkspace", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders dependency details from not_ready readiness responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: "not_ready",
            dependencies: {
              postgresql: { status: "ok" },
              neo4j: { status: "error", message: "bolt down" },
            },
          }),
          {
            status: 503,
            headers: { "content-type": "application/json" },
          },
        ),
      ),
    );

    renderUi(<ChainWorkspace />);

    await waitFor(() => {
      expect(screen.getByText("部分依赖不可用")).toBeInTheDocument();
    });
    expect(screen.getByText("neo4j: bolt down")).toBeInTheDocument();
    expect(screen.getByLabelText("max_paths")).toBeInTheDocument();
    expect(screen.getByLabelText("extra_depth")).toBeInTheDocument();
    expect(screen.getByLabelText("min_certainty_level")).toBeInTheDocument();
    expect(
      screen.queryByText("FigureChain API readiness 暂不可用。"),
    ).not.toBeInTheDocument();
  });

  it("submits excluded person and encounter ids from multipath filters", async () => {
    let submittedBody: unknown = null;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/figure-chain/health/ready") {
        return new Response(JSON.stringify(readyResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.startsWith("/api/figure-chain/people/search")) {
        const query = new URLSearchParams(url.split("?")[1]).get("q");
        return new Response(
          JSON.stringify({
            query,
            limit: 10,
            items: query === "韓琦" ? [hanQi] : [xuJi],
          }),
          {
            status: 200,
            headers: { "content-type": "application/json" },
          },
        );
      }
      if (url === "/api/figure-chain/chains/multipath") {
        submittedBody = JSON.parse(String(init?.body));
        return new Response(
          JSON.stringify({
            status: "no_path",
            source_person_id: xuJi.person_id,
            target_person_id: hanQi.person_id,
            max_depth: 12,
            max_paths: 5,
            extra_depth: 0,
            shortest_length: null,
            returned_paths: 0,
            paths: [],
            filters_applied: {
              min_certainty_level: "high",
              encounter_kinds: [],
              exclude_person_ids: ["38966b03-8aa7-5143-8021-2d266889b6c5"],
              exclude_encounter_ids: ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
              source_work_ids: [],
              intermediate_dynasty_codes: [],
              intermediate_year_min: null,
              intermediate_year_max: null,
            },
          }),
          {
            status: 200,
            headers: { "content-type": "application/json" },
          },
        );
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderUi(<ChainWorkspace />);

    await userEvent.type(screen.getByLabelText("起点人物"), "許幾");
    await screen.findByRole("button", { name: /选择 許幾/ });
    await userEvent.click(screen.getByRole("button", { name: /选择 許幾/ }));
    await userEvent.type(screen.getByLabelText("终点人物"), "韓琦");
    await screen.findByRole("button", { name: /选择 韓琦/ });
    await userEvent.click(screen.getByRole("button", { name: /选择 韓琦/ }));
    await userEvent.type(
      screen.getByLabelText("exclude_person_ids"),
      "38966b03-8aa7-5143-8021-2d266889b6c5",
    );
    await userEvent.type(
      screen.getByLabelText("exclude_encounter_ids"),
      "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
    );
    await userEvent.click(screen.getByRole("button", { name: "查询人物链" }));

    await waitFor(() => expect(submittedBody).not.toBeNull());
    expect(submittedBody).toMatchObject({
      filters: {
        exclude_person_ids: ["38966b03-8aa7-5143-8021-2d266889b6c5"],
        exclude_encounter_ids: ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
      },
    });
  });
});
