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
