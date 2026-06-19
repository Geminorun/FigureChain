import { expect, test } from "@playwright/test";

const candidateSummary = {
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
  latest_ai_job_status: null,
  has_ai_suggestion: false,
};

const candidateDetail = {
  ...candidateSummary,
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
  linked_encounter: null,
  latest_ai_suggestion: {
    suggestion_id: "6d027955-5a03-42a0-8425-f76b82073ebf",
    ai_run_id: "9d6958d5-c0e5-4112-9659-bb47c27cbdb7",
    status: "generated",
    recommendation: "promote",
    summary: "证据支持二人直接见面。",
    created_at: "2026-06-18T00:00:00Z",
  },
  ai_jobs: [],
};

const queuedAiJob = {
  id: "9d6958d5-c0e5-4112-9659-bb47c27cbdb7",
  job_type: "candidate_review_suggestion",
  target_type: "candidate",
  target_kind: "relationship",
  target_id: 960664,
  status: "queued",
  created_by: "lyl",
  params: {},
  result_ref_type: null,
  result_ref_id: null,
  error_code: null,
  error_message: null,
  queue_backend: "rq",
  queue_name: "figure-ai",
  queue_job_id: "rq-job-501",
  enqueued_at: "2026-06-19T00:00:01Z",
  attempt_count: 1,
  max_attempts: 3,
  next_run_at: null,
  cancel_requested_at: null,
  worker_id: "worker-1",
  heartbeat_at: "2026-06-19T00:00:02Z",
  started_at: null,
  finished_at: null,
  created_at: "2026-06-18T00:00:00Z",
  updated_at: "2026-06-18T00:00:00Z",
};

test("reviews a candidate through the workspace smoke path", async ({ page }) => {
  let promoteRequests = 0;

  await page.route("**/api/figure-chain/review/candidates?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ items: [candidateSummary], limit: 20, offset: 0, count: 1 }),
    });
  });
  await page.route("**/api/figure-chain/review/candidates/relationship/960664", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(candidateDetail),
    });
  });
  await page.route("**/api/figure-chain/ai/jobs?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ items: [queuedAiJob], count: 1, limit: 20 }),
    });
  });
  await page.route(`**/api/figure-chain/ai/jobs/${queuedAiJob.id}`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(queuedAiJob),
    });
  });
  await page.route(
    "**/api/figure-chain/review/candidates/relationship/960664/promote",
    async (route) => {
      promoteRequests += 1;
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          kind: "relationship",
          candidate_id: 960664,
          status: "promoted",
          reviewed_by: "lyl",
          encounter: null,
          message: null,
        }),
      });
    },
  );

  await page.goto("/review");

  await expect(page.getByRole("heading", { name: "候选审核工作台" })).toBeVisible();
  await expect(page.getByRole("button", { name: /relationship 960664/ })).toBeVisible();

  await page.getByRole("button", { name: /relationship 960664/ }).click();
  await expect(page.getByText("宋史")).toBeVisible();
  await expect(page.getByRole("heading", { name: "AI 建议" })).toBeVisible();
  await expect(page.getByText(/queue rq/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "审核动作" })).toBeVisible();

  await page.getByLabel("reviewed_by").fill("lyl");
  await page.getByLabel("evidence summary").fill("证据支持二人直接见面。");
  await page.getByRole("button", { name: "提升为 encounter" }).click();

  await expect.poll(() => promoteRequests).toBe(1);
});
