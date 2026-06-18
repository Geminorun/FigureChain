import { expect, test } from "@playwright/test";

const personId = "38966b03-8aa7-5143-8021-2d266889b6c5";
const otherPersonId = "46cfdf66-08c4-5876-964b-4a95d098afe9";
const encounterId = "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f";
const sourceWorkId = 7596;
const sourceRefId = 3853784;

const sourceWork = {
  source_work_id: sourceWorkId,
  text_code: 100,
  title_zh: "宋史",
  title_en: "Song History",
  source_name: "CBDB",
  source_table: "text_codes",
  source_pk: String(sourceWorkId),
  ref_count: 1,
  encounter_count: 1,
};

test("navigates person, encounter, and source evidence pages", async ({ page }) => {
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
        aliases: [],
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
  await page.route(`**/api/figure-chain/encounters/${encounterId}`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        encounter_id: encounterId,
        status: "active",
        encounter_kind: "direct_interaction",
        certainty_level: "high",
        path_eligible: true,
        source_work_id: sourceWorkId,
        pages: "11905",
        evidence_summary: "许几谒韩琦于魏",
        review_note: null,
        reviewed_by: "lyl",
        reviewed_at: "2026-06-09T00:00:00Z",
        person_a: {
          person_id: personId,
          cbdb_id: 780,
          display_name: "許幾",
          primary_name_zh_hant: "許幾",
          primary_name_zh_hans: "许几",
          primary_name_romanized: "Xu Ji",
          birth_year: 1054,
          death_year: 1115,
          external_ids: ["780"],
        },
        person_b: {
          person_id: otherPersonId,
          cbdb_id: 630,
          display_name: "韓琦",
          primary_name_zh_hant: "韓琦",
          primary_name_zh_hans: "韩琦",
          primary_name_romanized: "Han Qi",
          birth_year: 1008,
          death_year: 1075,
          external_ids: ["630"],
        },
        evidence: [
          {
            evidence_id: 12,
            candidate_table: "relationship_candidates",
            candidate_id: 960664,
            source_ref_id: sourceRefId,
            source_work_id: sourceWorkId,
            pages: "11905",
            evidence_kind: "candidate",
            evidence_summary: "许几谒韩琦于魏",
            created_at: "2026-06-09T00:00:00Z",
          },
        ],
        source_refs: [
          {
            source_ref_id: sourceRefId,
            source_work_id: sourceWorkId,
            title_zh: "宋史",
            title_en: null,
            pages: "11905",
            notes: "字先之，贵溪人，以诸生谒韩琦于魏。",
          },
        ],
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
            evidence_kind: "candidate",
            evidence_summary: "许几谒韩琦于魏",
            pages: "11905",
            created_at: "2026-06-09T00:00:00Z",
          },
        ],
      }),
    });
  });

  await page.goto(`/people/${personId}`);

  await expect(page.getByRole("heading", { name: "許幾" })).toBeVisible();
  await page.getByRole("link", { name: encounterId }).click();

  await expect(page).toHaveURL(new RegExp(`/encounters/${encounterId}$`));
  await expect(page.getByRole("heading", { name: "许几谒韩琦于魏" })).toBeVisible();
  await page.getByRole("link", { name: `source_ref ${sourceRefId}` }).first().click();

  await expect(page).toHaveURL(new RegExp(`/source-refs/${sourceRefId}$`));
  await expect(page.getByRole("heading", { name: `Source Ref ${sourceRefId}` })).toBeVisible();
  await expect(page.getByRole("link", { name: `Encounter ${encounterId}` })).toBeVisible();
  await expect(page.getByText("字先之，贵溪人，以诸生谒韩琦于魏。")).toBeVisible();
});
