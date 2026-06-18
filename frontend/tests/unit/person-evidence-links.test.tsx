import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChainPath } from "@/components/chain-path";
import { EncounterDetailPage } from "@/components/encounter-detail-page";
import { EvidencePanel } from "@/components/evidence-panel";
import { ReviewCandidateDetail } from "@/components/review-candidate-detail";
import { SelectedPersonCard } from "@/components/selected-person-card";
import type { ReviewCandidateDetail as ReviewCandidateDetailType } from "@/lib/figure-chain-types";
import { encounterDetail, oneHopPath, xuJi } from "@/test/fixtures";
import { renderUi } from "@/test/render";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const reviewDetail: ReviewCandidateDetailType = {
  kind: "relationship",
  candidate_id: 960664,
  person_a: {
    person_id: "38966b03-8aa7-5143-8021-2d266889b6c5",
    cbdb_id: 780,
    display_name: "許幾",
    primary_name_zh_hant: "許幾",
    primary_name_zh_hans: "许几",
    primary_name_romanized: "Xu Ji",
    birth_year: 1054,
    death_year: 1115,
  },
  person_b: {
    person_id: "46cfdf66-08c4-5876-964b-4a95d098afe9",
    cbdb_id: 630,
    display_name: "韓琦",
    primary_name_zh_hant: "韓琦",
    primary_name_zh_hans: "韩琦",
    primary_name_romanized: "Han Qi",
    birth_year: 1008,
    death_year: 1075,
  },
  relation: {
    relation_type: "visited",
    basis: "source_ref",
    strength: "high",
    notes: "direct visit",
    source_name: "CBDB",
    source_table: "assoc_data",
    source_pk: "960664",
  },
  time: { summary: "北宋", pages: "11905" },
  place: { summary: "魏" },
  status: "needs_review",
  confidence: 0.92,
  source_refs: [
    {
      source_ref_id: 3853784,
      source_work_id: 7596,
      title_zh: "宋史",
      title_en: null,
      pages: "11905",
      notes: "字先之，贵溪人，以诸生谒韩琦于魏。",
    },
  ],
  evidence: [
    {
      evidence_id: 1,
      source_ref_id: 3853784,
      evidence_kind: "source_ref",
      evidence_summary: "许几谒韩琦于魏",
      pages: "11905",
    },
  ],
  promotion_readiness: {
    default_promotable: true,
    default_path_eligible: true,
    reasons: ["high confidence direct interaction"],
  },
  linked_encounter: {
    encounter_id: "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
    status: "active",
  },
  latest_ai_suggestion: null,
  ai_jobs: [],
};

describe("person evidence links", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("links selected search people to person detail pages", () => {
    renderUi(<SelectedPersonCard label="起点" person={xuJi} onClear={vi.fn()} />);

    expect(screen.getByRole("link", { name: "許幾" })).toHaveAttribute(
      "href",
      `/people/${xuJi.person_id}`,
    );
  });

  it("links chain path people and encounter evidence to detail pages", () => {
    const onSelectEncounter = vi.fn();

    renderUi(<ChainPath path={oneHopPath} onSelectEncounter={onSelectEncounter} />);

    expect(screen.getByRole("link", { name: "許幾" })).toHaveAttribute(
      "href",
      "/people/38966b03-8aa7-5143-8021-2d266889b6c5",
    );
    expect(screen.getByRole("link", { name: "韓琦" })).toHaveAttribute(
      "href",
      "/people/46cfdf66-08c4-5876-964b-4a95d098afe9",
    );

    const encounterLink = screen.getByRole("link", {
      name: "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
    });
    expect(encounterLink).toHaveAttribute(
      "href",
      "/encounters/e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
    );
  });

  it("links evidence panel source refs and works to detail pages", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(encounterDetail)));

    renderUi(<EvidencePanel encounterId="evidence-panel-link-test" />);

    await screen.findByRole("heading", { name: "许几谒韩琦于魏" });
    expect(screen.getAllByRole("link", { name: "source_ref 3853784" })[0]).toHaveAttribute(
      "href",
      "/source-refs/3853784",
    );
    expect(screen.getByRole("link", { name: "source_work 7596" })).toHaveAttribute(
      "href",
      "/source-works/7596",
    );
  });

  it("links review candidate people and source refs when ids exist", () => {
    renderUi(<ReviewCandidateDetail detail={reviewDetail} error={null} isLoading={false} />);

    expect(screen.getByRole("link", { name: "許幾" })).toHaveAttribute(
      "href",
      "/people/38966b03-8aa7-5143-8021-2d266889b6c5",
    );
    expect(screen.getAllByRole("link", { name: "source_ref 3853784" })[0]).toHaveAttribute(
      "href",
      "/source-refs/3853784",
    );
  });

  it("renders encounter detail page with source ref and source work links", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(encounterDetail)));

    renderUi(<EncounterDetailPage encounterId="encounter-detail-link-test" />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "许几谒韩琦于魏" })).toBeInTheDocument();
    });
    expect(screen.getAllByRole("link", { name: "source_ref 3853784" })[0]).toHaveAttribute(
      "href",
      "/source-refs/3853784",
    );
    expect(screen.getByRole("link", { name: "source_work 7596" })).toHaveAttribute(
      "href",
      "/source-works/7596",
    );
  });
});
