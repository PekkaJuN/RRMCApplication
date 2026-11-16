import { readFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Year with products (specs/features/year-products.md, E2E tests). One receipt is typed in,
// dated this year, with a product name unique to the run and no category, so it shows under
// `Ei kategoriaa` whatever the other specs left in the database.

const RUN = Date.now();
const THIS_YEAR = new Date().getFullYear();
/** A product name of 100 characters (AC17). */
const LONG_NAME = `Vuosi ${RUN} `.padEnd(100, "x");

async function noViolations(page: Page): Promise<void> {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(result.violations).toEqual([]);
}

async function typeInReviewedReceipt(page: Page): Promise<void> {
  await page.goto("/kuitit");
  await page.getByRole("button", { name: "Uusi kuitti" }).click();
  const form = page.getByRole("form", { name: "Uusi kuitti" });
  await form.getByLabel("Kauppa").fill(`E2E-vuosi ${RUN}`);
  // June: no other journey uses this year's June, and the budget journey compares March.
  await form.getByLabel("Päivä", { exact: true }).fill(`15.06.${THIS_YEAR}`);
  await form.getByLabel("Loppusumma").fill("1,25");
  await form.getByRole("button", { name: "Luo kuitti" }).click();
  await expect(page).toHaveURL(/\/kuitit\/\d+$/);
  const newLine = page.getByRole("form", { name: "Uusi rivi" });
  await newLine.getByLabel("Tuote").fill(LONG_NAME);
  await newLine.getByLabel("Summa").fill("1,25");
  await newLine.getByRole("button", { name: "Lisää rivi" }).click();
  await expect(page.getByRole("textbox", { name: `Tuote: ${LONG_NAME}` })).toHaveValue(LONG_NAME);
  await page.getByRole("button", { name: "Vahvista" }).click();
  await expect(page.getByText("Vahvistettu")).toBeVisible();
}

test("year AC11, AC12, AC13, AC17, AC18: the Vuosi tuotteineen page", async ({ page }) => {
  await typeInReviewedReceipt(page);

  // AC11: the navigation item between Yhteenveto and Budjetti opens /vuosi.
  await page.goto("/");
  const navigation = page.getByRole("navigation", { name: "Päävalikko" });
  await expect(navigation.getByRole("link")).toHaveText([
    "Tuotteet",
    "Tuonti",
    "Kuitit",
    "Yhteenveto",
    "Vuosi tuotteineen",
    "Budjetti",
    "Vertailu",
    "Arkisto",
  ]);
  await navigation.getByRole("link", { name: "Vuosi tuotteineen" }).click();
  await expect(page).toHaveURL("/vuosi");
  await expect(navigation.getByRole("link", { name: "Vuosi tuotteineen" })).toHaveAttribute(
    "aria-current",
    "page",
  );

  // AC12: heading, table and no editing.
  await expect(page.getByRole("heading", { name: `Vuosi tuotteineen ${THIS_YEAR}` })).toBeVisible();
  const table = page.getByRole("table", { name: `Vuosi ${THIS_YEAR}` });
  await expect(table.getByRole("columnheader", { name: "Vuosi" })).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await expect(page.getByRole("combobox")).toHaveCount(0);
  await noViolations(page);

  // AC13: the product shows behind its category's toggle and hides again.
  await expect(table.getByText(LONG_NAME)).toHaveCount(0);
  await page.getByRole("button", { name: "Näytä tuotteet: Ei kategoriaa" }).click();
  await expect(table.getByText(LONG_NAME)).toBeVisible();
  await noViolations(page);
  await page.getByRole("button", { name: "Piilota tuotteet: Ei kategoriaa" }).click();
  await expect(table.getByText(LONG_NAME)).toHaveCount(0);
  await page.getByRole("button", { name: "Näytä tuotteet: Ei kategoriaa" }).click();

  // AC12: Vie CSV downloads vuosi_<year>.csv with the product.
  const started = page.waitForEvent("download");
  await page.getByRole("link", { name: "Vie CSV" }).click();
  const file = await started;
  expect(file.suggestedFilename()).toBe(`vuosi_${THIS_YEAR}.csv`);
  const text = (await readFile(await file.path())).toString("utf-8");
  expect(text).toContain(`;Ei kategoriaa;${LONG_NAME};1,25`);

  // AC17: the wide box, the sticky names and the wrapping long name.
  const measure = () =>
    page.evaluate((name) => {
      const box = document.querySelector(".archive-table")?.parentElement as HTMLElement;
      const span = Array.from(box.querySelectorAll(".archive-name span")).find(
        (element) => element.textContent === name,
      ) as HTMLElement;
      const header = span.closest("th") as HTMLElement;
      return {
        page: document.documentElement.scrollWidth,
        window: window.innerWidth,
        boxScroll: box.scrollWidth,
        boxClient: box.clientWidth,
        boxLeft: box.getBoundingClientRect().left,
        main: (document.querySelector("main") as HTMLElement).clientWidth,
        headerLeft: header.getBoundingClientRect().left,
        spanWidth: span.getBoundingClientRect().width,
        spanHeight: span.getBoundingClientRect().height,
        lineHeight: parseFloat(getComputedStyle(span).lineHeight) || 20,
      };
    }, LONG_NAME);

  await page.setViewportSize({ width: 1000, height: 800 });
  const narrow = await measure();
  expect(narrow.page).toBeLessThanOrEqual(narrow.window);
  expect(narrow.boxScroll).toBeGreaterThan(narrow.boxClient);
  expect(narrow.spanWidth).toBeLessThanOrEqual(250);
  expect(narrow.spanHeight).toBeGreaterThan(narrow.lineHeight);
  await page.evaluate(() => {
    const box = document.querySelector(".archive-table")?.parentElement as HTMLElement;
    box.scrollLeft = box.scrollWidth;
  });
  await expect(table.getByRole("columnheader", { name: `${THIS_YEAR}-12` })).toBeInViewport();
  const scrolled = await measure();
  expect(Math.abs(scrolled.headerLeft - scrolled.boxLeft)).toBeLessThanOrEqual(1);

  await page.setViewportSize({ width: 1600, height: 900 });
  const wide = await measure();
  expect(wide.boxClient).toBeGreaterThan(wide.main);
  expect(wide.page).toBeLessThanOrEqual(wide.window);
});
