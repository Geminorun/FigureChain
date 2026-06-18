import { expect, test } from "@playwright/test";

test("queries the real one-hop FigureChain sample", async ({ page }) => {
  await page.goto("/");

  await page.getByLabel("起点人物").fill("許幾");
  await page.getByRole("button", { name: /选择 許幾/ }).click();

  await page.getByLabel("终点人物").fill("韓琦");
  await page
    .getByRole("button", { name: /选择 韓琦 1008-1075 630/ })
    .click();

  await page.getByRole("button", { name: "查询人物链" }).click();

  await expect(page.getByText("找到 1 条路径")).toBeVisible();
  await expect(page.getByText(/path-1/)).toBeVisible();
  await expect(
    page.getByText("e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"),
  ).toBeVisible();

  await page.getByRole("button", { name: /查看证据/ }).click();
  await expect(page.getByText("Evidence")).toBeVisible();
  await expect(page.getByText("Source refs")).toBeVisible();
});
