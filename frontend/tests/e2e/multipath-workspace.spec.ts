import { expect, test } from "@playwright/test";

test("queries and renders multipath result", async ({ page }) => {
  await page.route("**/api/figure-chain/health/ready", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ status: "ready", dependencies: {} }),
    });
  });
  await page.route("**/api/figure-chain/people/search?**", async (route) => {
    const url = new URL(route.request().url());
    const query = url.searchParams.get("q") ?? "";
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        query,
        limit: 8,
        items: [
          {
            person_id: query.includes("韩") ? "target" : "source",
            display_name: query.includes("韩") ? "韩琦" : "许几",
            primary_name_zh_hant: null,
            primary_name_zh_hans: null,
            primary_name_romanized: null,
            birth_year: null,
            death_year: null,
            index_year: null,
            dynasty_code: null,
            matching_aliases: [],
            external_ids: [],
          },
        ],
      }),
    });
  });
  await page.route("**/api/figure-chain/chains/multipath", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "found",
        source_person_id: "source",
        target_person_id: "target",
        max_depth: 12,
        max_paths: 5,
        extra_depth: 0,
        shortest_length: 1,
        returned_paths: 1,
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
        paths: [
          {
            path_id: "path-1",
            rank: 1,
            chain_hash: "sha256:test",
            length: 1,
            quality_score: 1,
            people: [
              {
                person_id: "source",
                display_name: "许几",
                birth_year: null,
                death_year: null,
                cbdb_external_id: null,
              },
              {
                person_id: "target",
                display_name: "韩琦",
                birth_year: null,
                death_year: null,
                cbdb_external_id: null,
              },
            ],
            edges: [
              {
                encounter_id: "encounter-1",
                encounter_kind: "direct_interaction",
                certainty_level: "high",
                pages: null,
                evidence_summary: "见面",
              },
            ],
          },
        ],
      }),
    });
  });

  await page.goto("/");
  await page.getByLabel("起点人物").fill("许几");
  await page.getByRole("button", { name: /选择 许几/ }).click();
  await page.getByLabel("终点人物").fill("韩琦");
  await page.getByRole("button", { name: /选择 韩琦/ }).click();
  await page.getByRole("button", { name: "查询人物链" }).click();

  await expect(page.getByText("找到 1 条路径")).toBeVisible();
  await expect(page.getByText(/path-1/)).toBeVisible();
});
