import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

// Archiving (specs/features/archiving.md, E2E tests). The receipts are typed in and dated in
// the two years before this one, away from the receipts of the other specs. The database
// outlives a run: the journey deletes its archive at the end, and archiving a year that is
// already archived adds to it (agent decision 1), so a run that stopped half-way does not
// break the next. The year with an unreviewed receipt is another year, which stays blocked.

test.describe.configure({ mode: "serial" });

const RUN = Date.now();
const LAST_YEAR = new Date().getFullYear() - 1;
const BLOCKED_YEAR = LAST_YEAR - 1;
/** A product name of 100 characters (AC43). */
const LONG_NAME = `Pitkä ${RUN} `.padEnd(100, "x");

/** Type in a receipt with one line; waits for its page. */
async function typeInReceipt(page: Page, date: string, product: string): Promise<void> {
  await page.goto("/kuitit");
  await page.getByRole("button", { name: "Uusi kuitti" }).click();
  const form = page.getByRole("form", { name: "Uusi kuitti" });
  await form.getByLabel("Kauppa").fill(`E2E-arkisto ${RUN}`);
  await form.getByLabel("Päivä", { exact: true }).fill(date);
  await form.getByLabel("Loppusumma").fill("1,25");
  await form.getByRole("button", { name: "Luo kuitti" }).click();
  await expect(page).toHaveURL(/\/kuitit\/\d+$/);
  const newLine = page.getByRole("form", { name: "Uusi rivi" });
  await newLine.getByLabel("Tuote").fill(product);
  await newLine.getByLabel("Summa").fill("1,25");
  await newLine.getByRole("button", { name: "Lisää rivi" }).click();
  await expect(page.getByRole("textbox", { name: `Tuote: ${product}` })).toHaveValue(product);
}

function yearItem(page: Page, list: string, year: number): Locator {
  return page
    .getByRole("list", { name: list })
    .getByRole("listitem")
    .filter({ hasText: new RegExp(`^${year}:`) });
}

/** Opens every closed toggle of the year table, so all products show. */
async function openAll(page: Page): Promise<void> {
  const closed = page
    .getByRole("table", { name: `Vuosi ${LAST_YEAR}` })
    .locator("button[aria-expanded='false']");
  while ((await closed.count()) > 0) {
    await closed.first().click();
  }
}

async function noViolations(page: Page): Promise<void> {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(result.violations).toEqual([]);
}

test("archiving AC34: a year with an unreviewed receipt cannot be archived", async ({ page }) => {
  await typeInReceipt(page, `15.06.${BLOCKED_YEAR}`, "Maito");

  await page.goto("/arkisto");
  const item = yearItem(page, "Arkistoitavat vuodet", BLOCKED_YEAR);
  await expect(item).toContainText(/Tarkistamattomia kuitteja: \d+/);
  await expect(item.getByRole("button", { name: "Arkistoi" })).toHaveCount(0);
});

test("archiving AC33, AC39, AC40, AC43, AC22, AC38, AC42: archive, view and delete a year", async ({
  page,
}) => {
  await typeInReceipt(page, `15.03.${LAST_YEAR}`, LONG_NAME);
  await page.getByRole("button", { name: "Vahvista" }).click();
  await expect(page.getByText("Vahvistettu")).toBeVisible();

  // AC33: archive with the confirmation.
  await page.goto("/arkisto");
  await noViolations(page);
  const candidate = yearItem(page, "Arkistoitavat vuodet", LAST_YEAR);
  await candidate.getByRole("button", { name: "Arkistoi" }).click();
  await expect(candidate).toContainText(
    new RegExp(`Arkistoidaan vuosi ${LAST_YEAR}: \\d+ kuittia, \\d+ riviä ja \\d+ kuvaa\\.`),
  );
  await candidate.getByRole("button", { name: "Arkistoi" }).click();
  await expect(page.getByRole("main").getByRole("status")).toContainText(
    `Vuosi ${LAST_YEAR} arkistoitu`,
  );
  const archived = yearItem(page, "Arkistoidut vuodet", LAST_YEAR);
  await expect(archived).toBeVisible();
  await expect(yearItem(page, "Arkistoitavat vuodet", LAST_YEAR)).toHaveCount(0);
  // AC42: also the archived list with the result.
  await noViolations(page);

  // AC39, AC40: the year page, read-only, with products behind their category.
  await archived.getByRole("link", { name: "Näytä" }).click();
  await expect(page).toHaveURL(`/arkisto/${LAST_YEAR}`);
  const table = page.getByRole("table", { name: `Vuosi ${LAST_YEAR}` });
  await expect(table.getByRole("columnheader", { name: "Vuosi" })).toBeVisible();
  await expect(table.getByText(LONG_NAME)).toHaveCount(0);
  await openAll(page);
  await expect(table.getByText(LONG_NAME)).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await expect(page.getByRole("combobox")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Vie CSV" })).toHaveAttribute(
    "href",
    `/api/export/archive/${LAST_YEAR}`,
  );
  await noViolations(page);

  // AC43: the wide box, the sticky names and the wrapping long name.
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
  await expect(table.getByRole("columnheader", { name: `${LAST_YEAR}-12` })).toBeInViewport();
  const scrolled = await measure();
  expect(Math.abs(scrolled.headerLeft - scrolled.boxLeft)).toBeLessThanOrEqual(1);

  await page.setViewportSize({ width: 1600, height: 900 });
  const wide = await measure();
  expect(wide.boxClient).toBeGreaterThan(wide.main);
  expect(wide.page).toBeLessThanOrEqual(wide.window);

  // AC22: a period in the archived year says so.
  await page.goto(`/yhteenveto?unit=month&from=${LAST_YEAR}-03&to=${LAST_YEAR}-03`);
  await expect(page.getByText(`Arkistoitu vuosi ${LAST_YEAR} ei ole mukana.`)).toBeVisible();

  // AC38: delete the archive with the confirmation.
  await page.goto("/arkisto");
  const item = yearItem(page, "Arkistoidut vuodet", LAST_YEAR);
  await item.getByRole("button", { name: "Poista pysyvästi" }).click();
  await expect(item).toContainText(`Poistetaan vuoden ${LAST_YEAR} arkisto pysyvästi`);
  // AC42: also an open confirmation.
  await noViolations(page);
  await item.getByRole("button", { name: "Poista pysyvästi" }).click();
  await expect(page.getByRole("main").getByRole("status")).toContainText(
    `Vuoden ${LAST_YEAR} arkisto poistettu.`,
  );
  await expect(yearItem(page, "Arkistoidut vuodet", LAST_YEAR)).toHaveCount(0);
});

test("archiving AC41: a year that is not archived says so", async ({ page }) => {
  await page.goto(`/arkisto/${BLOCKED_YEAR}`);
  await expect(page.getByText(`Vuotta ${BLOCKED_YEAR} ei ole arkistossa.`)).toBeVisible();
  await noViolations(page);
});
