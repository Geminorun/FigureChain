import { describe, expect, it } from "vitest";

import type {
  AiJobCreateRequest,
  AiJobListResponse,
  AiJobResponse,
  ReviewActionRequest,
  ReviewActionResponse,
  ReviewCandidateDetail,
  ReviewCandidateListResponse,
  ReviewCandidateSummary,
} from "@/lib/figure-chain-types";

describe("review workspace API types", () => {
  it("models review candidate list responses", () => {
    const summary: ReviewCandidateSummary = {
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
      relation_type: "visited",
      time_summary: "北宋",
      place_summary: "魏",
      status: "needs_review",
      confidence: 0.92,
      evidence_count: 1,
      source_count: 1,
      promotion_readiness: {
        default_promotable: true,
        default_path_eligible: true,
        reasons: [],
      },
      latest_ai_job_status: "succeeded",
      has_ai_suggestion: true,
    };

    const response: ReviewCandidateListResponse = {
      items: [summary],
      limit: 20,
      offset: 0,
      count: 1,
    };

    expect(response.items[0]?.candidate_id).toBe(960664);
  });

  it("models review candidate details and actions", () => {
    const detail: ReviewCandidateDetail = {
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
        notes: null,
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
          title_zh: null,
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
        reasons: [],
      },
      linked_encounter: null,
      latest_ai_suggestion: {
        suggestion_id: "6d027955-5a03-42a0-8425-f76b82073ebf",
        ai_run_id: "9d6958d5-c0e5-4112-9659-bb47c27cbdb7",
        status: "generated",
        recommendation: "promote",
        summary: "证据支持二人直接见面。",
        created_at: "2026-06-18T00:00:00Z",
      },
      ai_jobs: [
        {
          run_id: "9d6958d5-c0e5-4112-9659-bb47c27cbdb7",
          status: "succeeded",
          purpose: "candidate_review_suggestion",
          created_at: "2026-06-18T00:00:00Z",
          finished_at: "2026-06-18T00:00:10Z",
        },
      ],
    };

    const request: ReviewActionRequest = {
      reviewed_by: "lyl",
      evidence_summary: "证据支持二人直接见面。",
      note: null,
      allow_non_default: false,
    };
    const response: ReviewActionResponse = {
      kind: detail.kind,
      candidate_id: detail.candidate_id,
      status: "promoted",
      reviewed_by: request.reviewed_by,
      encounter: {
        encounter_id: "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
        status: "active",
      },
      message: null,
    };

    expect(response.encounter?.status).toBe("active");
  });

  it("models AI job creation and polling responses", () => {
    const request: AiJobCreateRequest = {
      job_type: "candidate_review_suggestion",
      target_type: "review_candidate",
      target_kind: "relationship",
      target_id: 960664,
      created_by: "lyl",
      params: { language: "zh-Hans" },
    };
    const job: AiJobResponse = {
      id: "9d6958d5-c0e5-4112-9659-bb47c27cbdb7",
      job_type: request.job_type,
      target_type: request.target_type,
      target_kind: request.target_kind,
      target_id: request.target_id,
      status: "queued",
      created_by: request.created_by,
      params: request.params,
      result_ref_type: null,
      result_ref_id: null,
      error_code: null,
      error_message: null,
      started_at: null,
      finished_at: null,
      created_at: "2026-06-18T00:00:00Z",
      updated_at: "2026-06-18T00:00:00Z",
    };
    const list: AiJobListResponse = {
      items: [job],
      count: 1,
      limit: 20,
    };

    expect(list.items[0]?.status).toBe("queued");
  });
});
