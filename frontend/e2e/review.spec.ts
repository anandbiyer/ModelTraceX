import { expect, test } from "@playwright/test";

/**
 * P2-T6 exit E2E: upload → analyze (FakeProvider) → browse Review → expand a
 * table in Lineage → accept an edge → download DOCX. Matches the SDD Phase-2 exit.
 */
const M1 = "data work.staging; set raw.customer_events; run;";
const M2 = "data mart.customer_scores; set work.staging; run;";

test("upload, analyze, review, expand, accept an edge, download DOCX", async ({ page }) => {
  await page.goto("/");

  // Upload two SAS files (file stems drive the FakeProvider mapping).
  await page.getByTestId("file-input").setInputFiles([
    { name: "m1_build_staging.sas", mimeType: "text/plain", buffer: Buffer.from(M1) },
    { name: "m2_score.sas", mimeType: "text/plain", buffer: Buffer.from(M2) },
  ]);
  await expect(page.getByTestId("file-model-count")).toContainText("2 models");

  // A pre-flight estimate is available without spending tokens.
  await page.getByTestId("estimate").click();
  await expect(page.getByTestId("estimate")).toContainText("tokens");

  // Analyze; the run streams progress and auto-switches to Review on completion.
  await page.getByTestId("analyze").click();
  await expect(page.getByTestId("model-list")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("model-list")).toContainText("m1_build_staging");

  // Lineage: expand a table to column level, then select + accept an edge.
  await page.getByTestId("tab-Lineage").click();
  await expect(page.getByTestId("lineage-canvas")).toBeVisible();
  await page.locator('[data-testid^="expand-"]').first().click();
  await expect(page.locator('[data-testid^="columns-"]').first()).toBeVisible();

  await page.getByTestId("edge-list").locator("button").first().click();
  await expect(page.getByTestId("inspector")).toBeVisible();
  await page.getByTestId("accept").click();
  await expect(page.getByTestId("review-status")).toHaveText("Accepted");

  // Download the model DOCX from Review.
  await page.getByTestId("tab-Review").click();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("download-docx").click(),
  ]);
  expect(download.suggestedFilename()).toContain(".docx");
});
