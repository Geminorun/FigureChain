import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SourceRefDetailPage } from "@/components/source-ref-detail-page";
import { SourceWorkDetailPage } from "@/components/source-work-detail-page";
import { renderUi } from "@/test/render";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const sourceWork = {
  source_work_id: 1,
  text_code: 100,
  title_zh: "三國志",
  title_en: "Records of the Three Kingdoms",
  source_name: "CBDB",
  source_table: "TEXT_CODES",
  source_pk: "100",
  ref_count: 3,
  encounter_count: 2,
};

const sourceRef = {
  source_ref_id: 10,
  source_work: sourceWork,
  ref_source_table: "BIOG_MAIN",
  ref_source_pk: "25403",
  pages: "12a",
  notes: "原始引用",
  source_name: "CBDB",
  source_table: "BIOG_SOURCE_DATA",
  source_pk: "10",
  linked_encounter_evidence: [
    {
      evidence_id: 55,
      encounter_id: "00000000-0000-0000-0000-000000000101",
      evidence_kind: "candidate",
      evidence_summary: "有直接交往證據",
      pages: "12a",
      created_at: "2026-06-19T00:00:00Z",
    },
  ],
};

describe("source detail pages", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders source work metadata and counts", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(sourceWork)));

    renderUi(<SourceWorkDetailPage sourceWorkId="1" />);

    await screen.findByRole("heading", { name: "三國志" });
    expect(screen.getByText("text_code 100")).toBeInTheDocument();
    expect(screen.getByText("source refs 3")).toBeInTheDocument();
    expect(screen.getByText("encounters 2")).toBeInTheDocument();
  });

  it("renders source ref work link and linked encounter evidence", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(sourceRef)));

    renderUi(<SourceRefDetailPage sourceRefId="10" />);

    await screen.findByRole("heading", { name: "Source Ref 10" });
    expect(screen.getByRole("link", { name: "三國志" })).toHaveAttribute(
      "href",
      "/source-works/1",
    );
    expect(screen.getByRole("link", { name: "Encounter 00000000-0000-0000-0000-000000000101" })).toHaveAttribute(
      "href",
      "/encounters/00000000-0000-0000-0000-000000000101",
    );
    expect(screen.getByText("有直接交往證據")).toBeInTheDocument();
  });

  it("renders source work errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "source_work_not_found",
              message: "source work was not found",
              details: {},
            },
          },
          404,
        ),
      ),
    );

    renderUi(<SourceWorkDetailPage sourceWorkId="999" />);

    await screen.findByRole("alert");
  });
});
