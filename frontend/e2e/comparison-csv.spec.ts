import { readFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Comparison CSV export (specs/features/comparison-csv-export.md, AC16). The database
// outlives a run, so the journey checks the file's name and header row, not the sums; the
// backend tests read the figures.

const HEADER = "Jakso;Alkaa;Päättyy;Osittainen;Tyyppi;Nimi;Budjetti;Toteutunut;Jäljellä";

test("comparison CSV AC16: download the comparison with its weeks", async ({ page }) => {
  await page.goto("/vertailu?month=2026-10");
  const link = page.getByRole("link", { name: "Vie vertailu (CSV)" });
  await expect(link).toBeVisible();

  await page.getByRole("checkbox", { name: "Viikot mukaan" }).check();
  await expect(link).toHaveAttribute(
    "href",
    "/api/export/comparison?month=2026-10&period=calendar&weeks=true",
  );

  const response = await page.request.get((await link.getAttribute("href")) ?? "");
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toBe("text/csv; charset=utf-8");

  const started = page.waitForEvent("download");
  await link.click();
  const file = await started;
  expect(file.suggestedFilename()).toBe("vertailu_viikot_2026-10.csv");
  const bytes = await readFile(await file.path());
  // The byte order mark, so Excel reads the file as UTF-8.
  expect([...bytes.subarray(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
  expect(bytes.subarray(3).toString("utf-8").startsWith(`${HEADER}\r\n`)).toBe(true);

  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(result.violations).toEqual([]);
});
