import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

// PDF export (specs/features/pdf-export.md, E2E tests). The database outlives a run, so
// these journeys check the downloads and the links, not the sums; the backend tests read
// the files' content.

/** Click a PDF link; return the download's name and check that the file is a PDF. */
async function downloadPdf(page: Page, link: string): Promise<string> {
  const anchor = page.getByRole("link", { name: link });
  const href = await anchor.getAttribute("href");
  expect(href).not.toBeNull();
  const response = await page.request.get(href ?? "");
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toBe("application/pdf");

  const started = page.waitForEvent("download");
  await anchor.click();
  const file = await started;
  const bytes = await readFile(await file.path());
  expect(bytes.subarray(0, 5).toString("latin1")).toBe("%PDF-");
  return file.suggestedFilename();
}

test("PDF export AC19: download the weekly and monthly PDF of a month", async ({ page }) => {
  await page.goto("/yhteenveto?unit=month&from=2026-10&to=2026-10");
  await expect(page.getByRole("link", { name: "Vie viikkosummat (PDF)" })).toBeVisible();

  expect(await downloadPdf(page, "Vie viikkosummat (PDF)")).toBe(
    "summat_viikot_2026-10_2026-10.pdf",
  );
  expect(await downloadPdf(page, "Vie kuukausisummat (PDF)")).toBe(
    "summat_kuukaudet_2026-10_2026-10.pdf",
  );
});

test("PDF export AC20: a period over the limits shows the texts", async ({ page }) => {
  await page.goto("/yhteenveto?unit=month&from=2026-01&to=2027-01");
  await expect(page.getByRole("link", { name: "Vie rivit (CSV)" })).toBeVisible();

  await expect(page.getByText("Viikkosummien PDF: jakso enintään 31 päivää.")).toBeVisible();
  await expect(page.getByText("Kuukausisummien PDF: jakso enintään 366 päivää.")).toBeVisible();
  await expect(page.getByRole("link", { name: /\(PDF\)/ })).toHaveCount(0);
});

test("PDF export AC21: download the comparison PDF of a 15–14 period", async ({ page }) => {
  await page.goto("/vertailu");
  await page.getByRole("combobox", { name: "Jakso" }).selectOption({ label: "15.–14." });
  await page.getByLabel("Kuukausi").and(page.locator("input")).fill("2026-02");
  await expect(page).toHaveURL(/\/vertailu\?month=2026-02&period=mid$/);
  await expect(page.getByText("Jakso: 15.2.2026–14.3.2026")).toBeVisible();

  expect(await downloadPdf(page, "Vie vertailu (PDF)")).toBe("vertailu_15-14_2026-02.pdf");
});
