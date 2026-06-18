import { expect, test } from "@playwright/test";

const personId = "38966b03-8aa7-5143-8021-2d266889b6c5";
const otherPersonId = "46cfdf66-08c4-5876-964b-4a95d098afe9";
const encounterId = "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f";
const sourceWorkId = 7596;
const sourceRefId = 3853784;
const shareSlug = "stage5c-smoke";

const sourceWork = {
  source_work_id: sourceWorkId,
  text_code: 7596,
  title_zh: "宋史",
  title_en: "Song History",
  source_name: "CBDB",
  source_table: "text_codes",
  source_pk: String(sourceWorkId),
  ref_count: 1,
  encounter_count: 1,
};

const shareDetail = {
  id: "00000000-0000-0000-0000-0000000005c0",
  share_slug: shareSlug,
  url_path: `/share/${shareSlug}`,
  source_person_id: personId,
  target_person_id: otherPersonId,
  chain_hash: "stage5c-chain-hash",
  encounter_ids: [encounterId],
  path_payload: {
    length: 1,
    people: [
      {
        person_id: personId,
        display_name: "許幾",
        birth_year: 1054,
        death_year: 1115,
        cbdb_external_id: "780",
      },
      {
        person_id: otherPersonId,
        display_name: "韓琦",
        birth_year: 1008,
        death_year: 1075,
        cbdb_external_id: "630",
      },
    ],
    edges: [
      {
        encounter_id: encounterId,
        encounter_kind: "direct_interaction",
        certainty_level: "high",
        pages: "11905",
        evidence_summary: "许几谒韩琦于魏",
        source_refs: [
          {
            source_ref_id: sourceRefId,
            source_work_id: sourceWorkId,
          },
        ],
      },
    ],
  },
  filters_applied: { max_depth: 6, max_paths: 3 },
  include_ai_explanation: false,
  include_rag_context: false,
  schema_version: "share-v1",
  created_by: "acceptance",
  created_at: "2026-06-19T00:00:00Z",
};

test("stage 5C pages expose evidence, share snapshot, and markdown export", async ({
  page,
}) => {
  await page.route(`**/api/figure-chain/people/${personId}`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        person_id: personId,
        display_name: "許幾",
        primary_name_zh_hant: "許幾",
        primary_name_zh_hans: "许几",
        primary_name_romanized: "Xu Ji",
        birth_year: 1054,
        death_year: 1115,
        index_year: 780,
        floruit_start_year: null,
        floruit_end_year: null,
        dynasty_code: 15,
        dynasty_label_zh: "北宋",
        dynasty_label_en: "Northern Song",
        is_female: false,
        notes: "贵溪人",
        aliases: [{ alias_zh_hant: "許幾", alias_zh_hans: "许几", alias_romanized: "Xu Ji", alias_type_label_zh: "姓名", alias_type_label_en: "name" }],
        external_ids: [{ source_name: "CBDB", external_id: "780" }],
        encounter_summary: {
          active_count: 1,
          path_eligible_count: 1,
          high_certainty_count: 1,
        },
      }),
    });
  });
  await page.route(`**/api/figure-chain/people/${personId}/encounters?**`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            encounter_id: encounterId,
            other_person_id: otherPersonId,
            other_person_name: "韓琦",
            other_person_birth_year: 1008,
            other_person_death_year: 1075,
            encounter_kind: "direct_interaction",
            certainty_level: "high",
            path_eligible: true,
            source_work_id: sourceWorkId,
            source_title: "宋史",
            pages: "11905",
            evidence_summary: "许几谒韩琦于魏",
            status: "active",
            reviewed_by: "lyl",
            reviewed_at: "2026-06-09T00:00:00Z",
          },
        ],
        count: 1,
        limit: 50,
        offset: 0,
      }),
    });
  });
  await page.route(`**/api/figure-chain/source-refs/${sourceRefId}`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        source_ref_id: sourceRefId,
        source_work: sourceWork,
        ref_source_table: "text_data",
        ref_source_pk: String(sourceRefId),
        pages: "11905",
        notes: "字先之，贵溪人，以诸生谒韩琦于魏。",
        source_name: "CBDB",
        source_table: "source_refs",
        source_pk: String(sourceRefId),
        linked_encounter_evidence: [
          {
            evidence_id: 12,
            encounter_id: encounterId,
            evidence_kind: "reviewed",
            evidence_summary: "许几谒韩琦于魏",
            pages: "11905",
            created_at: "2026-06-09T00:00:00Z",
          },
        ],
      }),
    });
  });
  await page.route(`**/api/figure-chain/chains/share/${shareSlug}`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(shareDetail),
    });
  });
  await page.route("**/api/figure-chain/chains/export/markdown", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        content:
          "# FigureChain 人物链\n\n## 事实证据\n\n- Encounter e4f22ec2-22f7-4cda-bcc1-73aa83d0685f\n- source_ref 3853784\n",
        filename: "figurechain-stage5c-smoke.md",
        source_ids: {
          encounter_ids: [encounterId],
          source_ref_ids: [String(sourceRefId)],
          source_work_ids: [String(sourceWorkId)],
          ai_run_ids: [],
          retrieval_document_ids: [],
        },
      }),
    });
  });

  await page.goto(`/people/${personId}`);
  await expect(page.getByRole("heading", { name: "許幾" })).toBeVisible();
  await expect(page.getByText("CBDB")).toBeVisible();
  await expect(page.getByRole("link", { name: encounterId })).toBeVisible();

  await page.goto(`/source-refs/${sourceRefId}`);
  await expect(page.getByRole("heading", { name: `Source Ref ${sourceRefId}` })).toBeVisible();
  await expect(page.getByRole("link", { name: `Encounter ${encounterId}` })).toBeVisible();
  await expect(page.getByText("字先之，贵溪人，以诸生谒韩琦于魏。")).toBeVisible();

  await page.goto(`/share/${shareSlug}`);
  await expect(page.getByRole("heading", { name: "許幾 -> 韓琦" })).toBeVisible();
  await expect(page.getByRole("link", { name: `source_ref ${sourceRefId}` })).toBeVisible();
  await page.getByRole("button", { name: "导出 Markdown" }).click();
  await expect(page.getByText("figurechain-stage5c-smoke.md")).toBeVisible();
  await expect(page.getByLabel("Markdown 内容")).toContainText("source_ref 3853784");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载 Markdown" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("figurechain-stage5c-smoke.md");
});
