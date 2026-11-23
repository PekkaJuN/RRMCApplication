import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { syntheticPng } from "./synthetic";

// Receipt deletion and manual receipts (specs/features/receipt-management.md, E2E tests).
// The e2e container shares the E2E backend's failed folder (a test-only volume, see
// compose.yaml). It outlives a run and other journeys' failed imports land in it, so each
// test writes a uniquely named synthetic image and looks only for that name. The receipts
// are dated in September, away from the October receipts of the other specs.

const failedDir = process.env.E2E_FAILED_DIR ?? "";
const RUN = Date.now();

test.beforeAll(() => {
  expect(failedDir, "E2E_FAILED_DIR is set by compose.yaml").not.toBe("");
});

/** Open the new receipt form on the Kuitit page. */
async function openForm(page: Page): Promise<void> {
  await page.goto("/kuitit");
  await page.getByRole("button", { name: "Uusi kuitti" }).click();
  await expect(page.getByRole("form", { name: "Uusi kuitti" })).toBeVisible();
}

/** Fill the form's fields and create the receipt; waits for its page. */
async function create(page: Page, store: string): Promise<void> {
  const form = page.getByRole("form", { name: "Uusi kuitti" });
  await form.getByLabel("Kauppa").fill(store);
  await form.getByLabel("Päivä", { exact: true }).fill("15.09.2026");
  await form.getByLabel("Loppusumma").fill("1,25");
  await form.getByRole("button", { name: "Luo kuitti" }).click();
  await expect(page).toHaveURL(/\/kuitit\/\d+$/);
  await expect(page.getByRole("heading", { name: "Kuitti", exact: true })).toBeVisible();
}

test("AC29, AC11: type in a receipt without an image and add a line", async ({ page }) => {
  const store = `E2E-kauppa ${RUN} a`;
  await openForm(page);
  await create(page, store);

  await expect(page.getByText("Ei kuvaa.")).toBeVisible();
  await expect(page.getByRole("img")).toHaveCount(0);
  const newLine = page.getByRole("form", { name: "Uusi rivi" });
  await newLine.getByLabel("Tuote").fill("Maito");
  await newLine.getByLabel("Summa").fill("1,25");
  await newLine.getByRole("button", { name: "Lisää rivi" }).click();
  await expect(page.getByRole("textbox", { name: "Tuote: Maito" })).toHaveValue("Maito");

  await page.getByRole("link", { name: "Takaisin kuittilistaan" }).click();
  await expect(page.getByRole("table", { name: "Kuittilista" }).getByText(store)).toBeVisible();
});

test("date-field AC14, AC8: a date typed as dd.mm.yyyy is saved", async ({ page }) => {
  await openForm(page);
  await create(page, `E2E-kauppa ${RUN} pvm`);
  const date = page.getByLabel("Päivä", { exact: true });
  await expect(date).toHaveValue("15.09.2026");

  await date.fill("16.9.2026");
  const saved = page.waitForResponse((answer) => answer.request().method() === "PATCH");
  await date.press("Enter");
  await saved;
  await page.reload();

  await expect(page.getByLabel("Päivä", { exact: true })).toHaveValue("16.09.2026");
});

test("AC30: type in a failed receipt with its image", async ({ page }) => {
  const name = `epaonnistunut-${RUN}.png`;
  await writeFile(join(failedDir, name), syntheticPng(`failed ${RUN}`));
  await openForm(page);

  await page.getByLabel("Kuva").selectOption(name);
  const preview = page.getByRole("img", { name: "Valittu kuva" });
  await expect(preview).toBeVisible();
  expect(await preview.evaluate((element) => (element as HTMLImageElement).naturalWidth)).toBe(1);
  await create(page, `E2E-kauppa ${RUN} b`);

  await expect(page.getByRole("img", { name: "Kuitin kuva" })).toBeVisible();
  await openForm(page);
  await expect(page.getByLabel("Kuva").locator("option", { hasText: name })).toHaveCount(0);
});

test("AC25: delete a receipt from its page", async ({ page }) => {
  const store = `E2E-kauppa ${RUN} c`;
  await openForm(page);
  await create(page, store);

  await page.getByRole("button", { name: "Poista kuitti" }).click();
  const controls = page.getByRole("button", { name: "Vahvista" }).locator("..");
  await controls.getByRole("button", { name: "Poista", exact: true }).click();

  await expect(page).toHaveURL(/\/kuitit$/);
  await expect(page.getByRole("heading", { name: "Kuitit", exact: true })).toBeVisible();
  await expect(page.getByText(store)).toHaveCount(0);
});

/** The axe violations of the page: rule id and the first targets of each. */
async function axeViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return results.violations.map(
    (violation) =>
      `${violation.id}: ${violation.nodes
        .slice(0, 3)
        .map((node) => node.target.join(" "))
        .join(", ")}`,
  );
}

test("AC35: the new receipt form and a receipt without an image are accessible", async ({
  page,
}) => {
  const name = `saavutettavuus-${RUN}.png`;
  await writeFile(join(failedDir, name), syntheticPng(`axe ${RUN}`));
  await openForm(page);
  await page.getByLabel("Kuva").selectOption(name);
  await expect(page.getByRole("img", { name: "Valittu kuva" })).toBeVisible();
  const form = await axeViolations(page);

  await page.getByRole("form", { name: "Uusi kuitti" }).getByLabel("Kuva").selectOption("");
  await create(page, `E2E-kauppa ${RUN} d`);
  await expect(page.getByText("Ei kuvaa.")).toBeVisible();
  const receipt = await axeViolations(page);

  expect({ form, receipt }).toEqual({ form: [], receipt: [] });
});

// Note on old and undated unreviewed receipts (specs/features/unreviewed-receipts-note.md,
// E2E tests). The receipts are dated two years back: the archiving journey archives last
// year, and an unreviewed receipt there would block it; two years back is its blocked year.
const OLD_YEAR = new Date().getFullYear() - 2;

/** Type in a receipt dated in OLD_YEAR with one line, and confirm it when `review` is set. */
async function typeInOld(page: Page, store: string, review: boolean): Promise<void> {
  await openForm(page);
  const form = page.getByRole("form", { name: "Uusi kuitti" });
  await form.getByLabel("Kauppa").fill(store);
  await form.getByLabel("Päivä", { exact: true }).fill(`15.09.${OLD_YEAR}`);
  await form.getByLabel("Loppusumma").fill("1,25");
  await form.getByRole("button", { name: "Luo kuitti" }).click();
  await expect(page).toHaveURL(/\/kuitit\/\d+$/);
  if (review) {
    const newLine = page.getByRole("form", { name: "Uusi rivi" });
    await newLine.getByLabel("Tuote").fill("Maito");
    await newLine.getByLabel("Summa").fill("1,25");
    await newLine.getByRole("button", { name: "Lisää rivi" }).click();
    await expect(page.getByRole("textbox", { name: "Tuote: Maito" })).toHaveValue("Maito");
    await page.getByRole("button", { name: "Vahvista" }).click();
    await expect(page.getByText("Vahvistettu")).toBeVisible();
  }
}

test("unreviewed-note AC5, AC6, AC9: show only the old unreviewed receipts", async ({ page }) => {
  const unreviewed = `E2E-vanha ${RUN} a`;
  const reviewed = `E2E-vanha ${RUN} b`;
  await typeInOld(page, unreviewed, false);
  await typeInOld(page, reviewed, true);

  await page.goto("/kuitit");
  const table = page.getByRole("table", { name: "Kuittilista" });
  const note = page.getByRole("main").getByRole("status");
  await expect(note).toContainText(
    new RegExp(
      String.raw`Tarkistamattomia kuitteja edellisiltä vuosilta: \d+ \(.*${OLD_YEAR}.*\)\.`,
    ),
  );
  await expect(table.getByText(unreviewed)).toBeVisible();
  await expect(table.getByText(reviewed)).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);

  // AC5 with the keyboard: Enter turns the filter on.
  const button = note.getByRole("button", { name: "Näytä vain nämä kuitit" });
  await button.focus();
  await page.keyboard.press("Enter");
  await expect(button).toHaveAttribute("aria-pressed", "true");
  await expect(table.getByText(unreviewed)).toBeVisible();
  await expect(table.getByText(reviewed)).toHaveCount(0);
  await expect(table.getByText("Vahvistettu")).toHaveCount(0);
  expect(await axeViolations(page)).toEqual([]);

  // AC6 with the keyboard: Space turns it off.
  await page.keyboard.press("Space");
  await expect(button).toHaveAttribute("aria-pressed", "false");
  await expect(table.getByText(reviewed)).toBeVisible();
});

// Receipt search (specs/features/receipt-search.md, E2E tests). The line names carry RUN,
// so the search finds only this run's receipts among those of other journeys.

/** Type in a receipt with one line, and give the line `category` when it is set. */
async function typeInWithLine(
  page: Page,
  store: string,
  line: string,
  category?: string,
): Promise<void> {
  await openForm(page);
  await create(page, store);
  const newLine = page.getByRole("form", { name: "Uusi rivi" });
  await newLine.getByLabel("Tuote").fill(line);
  await newLine.getByLabel("Summa").fill("1,25");
  await newLine.getByRole("button", { name: "Lisää rivi" }).click();
  await expect(page.getByRole("textbox", { name: `Tuote: ${line}` })).toHaveValue(line);
  if (category) {
    const saved = page.waitForResponse((answer) => answer.request().method() === "PATCH");
    await page.getByRole("combobox", { name: `Kategoria: ${line}` }).selectOption({
      label: category,
    });
    await saved;
  }
}

test("receipt search AC9: search the receipts by a product name", async ({ page }) => {
  const withProduct = `E2E-haku ${RUN} a`;
  const other = `E2E-haku ${RUN} b`;
  await typeInWithLine(page, withProduct, `Hakutuote${RUN}`);
  await typeInWithLine(page, other, `Muutuote${RUN}`);

  await page.goto("/kuitit");
  const table = page.getByRole("table", { name: "Kuittilista" });
  await expect(table.getByText(other)).toBeVisible();
  // Store search AC9 renamed the field from "Hae tuotteella" (store search P6).
  const field = page.getByRole("searchbox", { name: "Hakusana" });
  await field.fill(`  HAKUTUOTE${RUN}  `);
  await field.press("Enter");

  await expect(table.getByText(other)).toHaveCount(0);
  await expect(table.getByText(withProduct)).toBeVisible();
  await expect(table.getByRole("row")).toHaveCount(2);
  expect(await axeViolations(page)).toEqual([]);

  await field.fill("");
  await page.getByRole("button", { name: "Hae", exact: true }).click();
  await expect(table.getByText(other)).toBeVisible();
  await expect(table.getByText(withProduct)).toBeVisible();
});

test("receipt search AC10: show the receipts with lines without a category", async ({ page }) => {
  const uncategorized = `E2E-haku ${RUN} c`;
  const categorized = `E2E-haku ${RUN} d`;
  await typeInWithLine(page, uncategorized, `Ilmankategoriaa${RUN}`);
  await typeInWithLine(page, categorized, `Kategorialla${RUN}`, "Leivät");

  await page.goto("/kuitit");
  const table = page.getByRole("table", { name: "Kuittilista" });
  const field = page.getByRole("searchbox", { name: "Hakusana" });
  await field.fill(`${RUN}`);
  await field.press("Enter");
  await expect(table.getByText(categorized)).toBeVisible();
  await expect(table.getByText(uncategorized)).toBeVisible();

  await page
    .getByRole("checkbox", { name: "Vain kuitit, joilla on rivejä ilman kategoriaa" })
    .check();

  await expect(table.getByText(categorized)).toHaveCount(0);
  await expect(table.getByText(uncategorized)).toBeVisible();
});

// Store search (specs/features/store-search.md, E2E tests). The stores carry RUN, so the
// search finds only this run's receipts among those of other journeys.

test("store search AC10, AC11: search the receipts by a part of the store", async ({ page }) => {
  const wanted = `E2E-kauppahaku ${RUN} Alfa`;
  const other = `E2E-kauppahaku ${RUN} Beeta`;
  await openForm(page);
  await create(page, wanted);
  await openForm(page);
  await create(page, other);

  await page.goto("/kuitit");
  const table = page.getByRole("table", { name: "Kuittilista" });
  await expect(table.getByText(other)).toBeVisible();
  await page.getByRole("radio", { name: "Kauppa" }).check();
  const field = page.getByRole("searchbox", { name: "Hakusana" });
  await field.fill(`kauppahaku ${RUN} ALF`);
  await field.press("Enter");

  await expect(table.getByText(other)).toHaveCount(0);
  await expect(table.getByText(wanted)).toBeVisible();
  await expect(table.getByRole("row")).toHaveCount(2);
  expect(await axeViolations(page)).toEqual([]);

  // AC11: Tuote searches again with the same text; no line name contains it.
  await page.getByRole("radio", { name: "Tuote" }).check();
  await expect(page.getByText("Hakuehdoilla ei löytynyt kuitteja.")).toBeVisible();
  await expect(page.getByRole("table", { name: "Kuittilista" })).toHaveCount(0);
});
