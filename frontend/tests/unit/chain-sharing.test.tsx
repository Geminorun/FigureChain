import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChainShareActions } from "@/components/chain-share-actions";
import { SharePage } from "@/components/share-page";
import type { MultiPathChainResponse, MultiPathItem } from "@/lib/figure-chain-types";
import { renderUi } from "@/test/render";

const path: MultiPathItem = {
  path_id: "path-1",
  rank: 1,
  chain_hash: "known-chain-hash",
  length: 1,
  quality_score: 1,
  people: [
    {
      person_id: "38966b03-8aa7-5143-8021-2d266889b6c5",
      display_name: "許幾",
      birth_year: 1054,
      death_year: 1115,
      cbdb_external_id: "780",
    },
    {
      person_id: "46cfdf66-08c4-5876-964b-4a95d098afe9",
      display_name: "韓琦",
      birth_year: 1008,
      death_year: 1075,
      cbdb_external_id: "630",
    },
  ],
  edges: [
    {
      encounter_id: "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
      encounter_kind: "direct_interaction",
      certainty_level: "high",
      pages: "11905",
      evidence_summary: "许几谒韩琦于魏",
    },
  ],
};

const result: MultiPathChainResponse = {
  status: "found",
  source_person_id: path.people[0].person_id,
  target_person_id: path.people[1].person_id,
  max_depth: 12,
  max_paths: 5,
  extra_depth: 0,
  shortest_length: 1,
  returned_paths: 1,
  paths: [path],
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
};

const shareDetail = {
  id: "00000000-0000-0000-0000-000000000501",
  share_slug: "20260619-test",
  url_path: "/share/20260619-test",
  source_person_id: path.people[0].person_id,
  target_person_id: path.people[1].person_id,
  chain_hash: "known-chain-hash",
  encounter_ids: ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
  path_payload: {
    length: 1,
    people: path.people,
    edges: [
      {
        ...path.edges[0],
        source_refs: [{ source_ref_id: 3853784, source_work_id: 7596 }],
      },
    ],
  },
  filters_applied: result.filters_applied,
  include_ai_explanation: false,
  include_rag_context: false,
  schema_version: "share-v1",
  created_by: "lyl",
  created_at: "2026-06-19T00:00:00Z",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("chain sharing frontend", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates share snapshot from the selected path and displays share URL", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ share_slug: "20260619-test", url_path: "/share/20260619-test" }));
    vi.stubGlobal("fetch", fetchMock);

    renderUi(<ChainShareActions path={path} result={result} />);
    await userEvent.click(screen.getByRole("button", { name: "创建分享链接" }));

    await screen.findByText("/share/20260619-test");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/figure-chain/chains/share",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"chain_hash":"known-chain-hash"'),
      }),
    );
    expect(fetchMock.mock.calls[0][1].body).toContain(
      '"encounter_id":"e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"',
    );
  });

  it("exports markdown after share creation and exposes content", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ share_slug: "20260619-test", url_path: "/share/20260619-test" }))
        .mockResolvedValueOnce(
          jsonResponse({
            content: "# FigureChain 人物链\n",
            filename: "figurechain-known-chain-hash.md",
            source_ids: {
              encounter_ids: ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
              source_ref_ids: ["3853784"],
              source_work_ids: ["7596"],
              ai_run_ids: [],
              retrieval_document_ids: [],
            },
          }),
        ),
    );

    renderUi(<ChainShareActions path={path} result={result} />);
    await userEvent.click(screen.getByRole("button", { name: "创建分享链接" }));
    await screen.findByText("/share/20260619-test");
    await userEvent.click(screen.getByRole("button", { name: "导出 Markdown" }));

    await screen.findByText("figurechain-known-chain-hash.md");
    expect(screen.getByLabelText("Markdown 内容")).toHaveValue("# FigureChain 人物链\n");
    expect(screen.getByRole("button", { name: "复制 Markdown" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "下载 Markdown" })).toBeEnabled();
  });

  it("disables copy and download buttons when export fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ share_slug: "20260619-test", url_path: "/share/20260619-test" }))
        .mockResolvedValueOnce(
          jsonResponse(
            {
              error: {
                code: "export_format_not_supported",
                message: "format not supported",
                details: {},
              },
            },
            400,
          ),
        ),
    );

    renderUi(<ChainShareActions path={path} result={result} />);
    await userEvent.click(screen.getByRole("button", { name: "创建分享链接" }));
    await screen.findByText("/share/20260619-test");
    await userEvent.click(screen.getByRole("button", { name: "导出 Markdown" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "复制 Markdown" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "下载 Markdown" })).toBeDisabled();
  });

  it("renders share page facts and source ids", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(shareDetail)));

    renderUi(<SharePage shareSlug="20260619-test" />);

    await screen.findByRole("heading", { name: "許幾 -> 韓琦" });
    expect(screen.getByText("known-chain-hash")).toBeInTheDocument();
    expect(screen.getByText("许几谒韩琦于魏")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Encounter e4f22ec2-22f7-4cda-bcc1-73aa83d0685f" })).toHaveAttribute(
      "href",
      "/encounters/e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
    );
    expect(screen.getByRole("link", { name: "source_ref 3853784" })).toHaveAttribute(
      "href",
      "/source-refs/3853784",
    );
  });
});
