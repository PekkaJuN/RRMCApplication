import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

// Monthly budget (specs/features/budget.md, E2E tests). The import journeys empty the import
// folder, so these receipts are typed in. They are dated in March, away from the receipts of
// the other specs, but the database outlives a run, so the tests compare the page with its
// own earlier value instead of assuming an empty month.

const RUN = Date.now();
const RECEIPT_DATE = "10.03.2026";

function comparisonTotal(page: Page): Locator {
  return page.getByRole("table", { name: "Kuukausi" }).getByRole("row", { name: /Yhteensä/ });
}

/** The spending in the `Yhteensä` row of the month table, in cents. */
async function actualCents(page: Page): Promise<number> {
  const text = await comparisonTotal(page).getByRole("cell").nth(1).textContent();
  return Number((text ?? "").replace(/[^0-9]/g, ""));
}

/** Type in a receipt with one line; waits for its page. */
async function typeInReceipt(page: Page, store: string): Promise<void> {
  await page.goto("/kuitit");
  await page.getByRole("button", { name: "Uusi kuitti" }).click();
  const form = page.getByRole("form", { name: "Uusi kuitti" });
  await form.getByLabel("Kauppa").fill(store);
  await form.getByLabel("Päivä", { exact: true }).fill(RECEIPT_DATE);
  await form.getByLabel("Loppusumma").fill("1,25");
  await form.getByRole("button", { name: "Luo kuitti" }).click();
  await expect(page).toHaveURL(/\/kuitit\/\d+$/);
  const newLine = page.getByRole("form", { name: "Uusi rivi" });
  await newLine.getByLabel("Tuote").fill("Maito");
  await newLine.getByLabel("Summa").fill("1,25");
  await newLine.getByRole("button", { name: "Lisää rivi" }).click();
  await expect(page.getByRole("textbox", { name: "Tuote: Maito" })).toHaveValue("Maito");
}

async function confirmReceipt(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Vahvista" }).click();
  await expect(page.getByText("Vahvistettu")).toBeVisible();
}

test("AC17, AC19, AC7: set a budget and compare a month", async ({ page }) => {
  const euros = String((RUN % 900) + 100);
  await page.goto("/budjetti");
  const field = page.getByRole("textbox", { name: "Auto" });
  await field.fill(euros);
  await field.blur();
  await expect(field).toHaveValue(`${euros},00`);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.reload();
  await expect(field).toHaveValue(`${euros},00`);

  await page.goto("/vertailu?month=2026-03");
  await expect(comparisonTotal(page)).toBeVisible();
  const before = await actualCents(page);

  await typeInReceipt(page, `E2E-budjetti ${RUN} a`);
  const receiptUrl = page.url();
  await page.goto("/vertailu?month=2026-03");
  await expect(comparisonTotal(page)).toBeVisible();
  await expect(page.getByText(/Tarkistamattomia kuitteja, ei mukana:/)).toBeVisible();
  expect(await actualCents(page)).toBe(before);

  await page.goto(receiptUrl);
  await confirmReceipt(page);
  await page.goto("/vertailu?month=2026-03");
  await expect(comparisonTotal(page)).toBeVisible();
  expect(await actualCents(page)).toBe(before + 125);
  await expect(
    page.getByRole("table", { name: "Kuukausi" }).getByRole("row", { name: /Auto/ }),
  ).toContainText(`${euros},00 €`);

  await page.getByRole("button", { name: "Näytä viikot" }).click();
  await expect(page.getByRole("table", { name: "Viikot" })).toBeVisible();
});

test("AC26, AC31: compare a period from the 15th to the 14th", async ({ page }) => {
  await page.goto("/vertailu");
  await page.getByRole("combobox", { name: "Jakso" }).selectOption({ label: "15.–14." });
  await expect(page).toHaveURL(/\/vertailu\?month=\d{4}-\d{2}&period=mid$/);
  await page.getByLabel("Kuukausi").and(page.locator("input")).fill("2026-02");
  await expect(page).toHaveURL(/\/vertailu\?month=2026-02&period=mid$/);
  await expect(page.getByText("Jakso: 15.2.2026–14.3.2026")).toBeVisible();
  await expect(comparisonTotal(page)).toBeVisible();
  const before = await actualCents(page);

  await typeInReceipt(page, `E2E-budjetti ${RUN} b`);
  await confirmReceipt(page);

  await page.goto("/vertailu?month=2026-02&period=mid");
  await expect(comparisonTotal(page)).toBeVisible();
  expect(await actualCents(page)).toBe(before + 125);
});

test("AC34: the week table uses the window's width", async ({ page }) => {
  const widths = (target: Page) =>
    target.evaluate(() => {
      const box = document.querySelector("table[aria-label='Viikot']")?.parentElement;
      return {
        page: document.documentElement.scrollWidth,
        scroll: box?.scrollWidth ?? 0,
        client: box?.clientWidth ?? 0,
      };
    });

  await page.setViewportSize({ width: 1920, height: 1080 });
  // March 2026 holds six ISO weeks: W09 (Sunday 1.3.) to W14.
  await page.goto("/vertailu?month=2026-03");
  await page.getByRole("button", { name: "Näytä viikot" }).click();
  await expect(page.getByRole("table", { name: "Viikot" })).toBeVisible();
  const wide = await widths(page);
  expect(wide.client).toBeGreaterThan(1200);
  expect(wide.scroll).toBe(wide.client);
  expect(wide.page).toBeLessThanOrEqual(1920);

  await page.setViewportSize({ width: 600, height: 800 });
  const narrow = await widths(page);
  expect(narrow.page).toBeLessThanOrEqual(600);
  expect(narrow.scroll).toBeGreaterThan(narrow.client);
});

test("NFR-16: the budget pages have no WCAG 2.1 AA violation", async ({ page }) => {
  await page.goto("/budjetti");
  await expect(page.getByRole("textbox", { name: "Auto" })).toBeVisible();
  const budget = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(budget.violations).toEqual([]);

  await page.goto("/vertailu?month=2026-03&period=mid");
  await page.getByRole("button", { name: "Näytä viikot" }).click();
  await expect(page.getByRole("table", { name: "Viikot" })).toBeVisible();
  const comparison = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(comparison.violations).toEqual([]);
});
