import { readdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";

// The e2e container shares the E2E backend's import folder (a test-only volume, see
// compose.yaml). A duplicate stays there by design, so files of an earlier run are removed
// first; the folder only ever holds this test's synthetic files.
const importDir = process.env.E2E_IMPORT_DIR ?? "";

// `run --rm` leaves backend-e2e running with its database and the previous run's report, so
// names and bytes are unique per run: a new image hash, and a report that cannot be the old one.
const RUN = Date.now();
const ORIGINAL = `kuitti-${RUN}.jpg`;
const COPY = `kuitti-${RUN}_kopio.jpg`; // after ORIGINAL in name order, so it is the duplicate
const NOTE = `muistio-${RUN}.txt`;

/** JPEG-signed synthetic bytes; not a real image. */
const SYNTHETIC_JPEG = Buffer.concat([
  Buffer.from([0xff, 0xd8, 0xff, 0xe0]),
  Buffer.from(`synthetic e2e image ${RUN}`),
]);

test.beforeAll(async () => {
  expect(importDir, "E2E_IMPORT_DIR is set by compose.yaml").not.toBe("");
  for (const name of await readdir(importDir)) {
    await rm(join(importDir, name), { recursive: true });
  }
});

test("AC1, AC4, AC6, AC26, AC27: import receipts from the Tuonti page", async ({ page }) => {
  await writeFile(join(importDir, ORIGINAL), SYNTHETIC_JPEG);
  await writeFile(join(importDir, COPY), SYNTHETIC_JPEG);
  await writeFile(join(importDir, NOTE), "synthetic note");

  await page.goto("/");
  await page
    .getByRole("navigation", { name: "Päävalikko" })
    .getByRole("link", { name: "Tuonti" })
    .click();
  await expect(page.getByRole("heading", { name: "Tuonti" })).toBeVisible();
  await page.getByRole("button", { name: "Tuo kuitit" }).click();

  // The names are new, so these match only this run's report.
  const report = page.getByRole("region", { name: "Edellinen tuonti" });
  await expect(
    report.getByRole("list", { name: "Jo tuodut kuvat (jätetty tuontikansioon)" }),
  ).toHaveText(COPY);
  await expect(
    report.getByRole("list", { name: "Epäonnistuneet (siirretty epäonnistuneiden kansioon)" }),
  ).toHaveText(`${NOTE}: Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa.`);
  await expect(report.getByText("Tuotu: 1")).toBeVisible();
  await expect(report.getByText("Kaksoiskappaleita: 1")).toBeVisible();
  await expect(report.getByText("Epäonnistui: 1")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

// The fake reader fails exactly these bytes (backend FAKE_PARSE_FAILED_IMAGE, receipt-reading AC24b).
const FAKE_PARSE_FAILED_IMAGE = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  Buffer.from("rrmc fake reader: parse_failed"),
]);

test("receipt-reading AC24b, AC27: a receipt that cannot be read is reported", async ({ page }) => {
  const unreadable = `parse-failed-${RUN}.png`;
  await writeFile(join(importDir, unreadable), FAKE_PARSE_FAILED_IMAGE);

  await page.goto("/");
  await page
    .getByRole("navigation", { name: "Päävalikko" })
    .getByRole("link", { name: "Tuonti" })
    .click();
  await page.getByRole("button", { name: "Tuo kuitit" }).click();

  const report = page.getByRole("region", { name: "Edellinen tuonti" });
  await expect(
    report.getByRole("list", { name: "Epäonnistuneet (siirretty epäonnistuneiden kansioon)" }),
  ).toHaveText(`${unreadable}: Kuittia ei voitu tulkita.`);
  await expect(report.getByText("Tuotu: 0")).toBeVisible();
  await expect(report.getByText("Epäonnistui: 1")).toBeVisible();
});

// Receipt review AC31. The fake reader gives every image Testikauppa, 5.10.2026, Maito 1,25 €
// and Limu 2,24 €, total 3,49 €. The database lives as long as backend-e2e, so an earlier run
// may already have remembered Maito.
test("receipt-review AC31: review, correct and confirm an imported receipt", async ({ page }) => {
  await writeFile(
    join(importDir, `kuitti-${RUN}_tarkistus.jpg`),
    Buffer.concat([SYNTHETIC_JPEG, Buffer.from(" review")]),
  );
  const navigation = page.getByRole("navigation", { name: "Päävalikko" });
  await page.goto("/tuonti");
  await page.getByRole("button", { name: "Tuo kuitit" }).click();
  const report = page.getByRole("region", { name: "Edellinen tuonti" });
  await expect(report.getByText("Tuotu: 1")).toBeVisible();

  await navigation.getByRole("link", { name: "Kuitit" }).click();
  // Same-date receipts list the newest import first, so the first one is this run's.
  await page
    .getByRole("table", { name: "Kuittilista" })
    .getByRole("link", { name: "5.10.2026" })
    .first()
    .click();
  await expect(page.getByRole("heading", { name: "Kuitti", exact: true })).toBeVisible();

  const milk = page.getByRole("combobox", { name: "Kategoria: Maito" });
  await expect(milk).toBeEnabled();
  const current = await milk.locator("option:checked").textContent();
  const chosen = current === "Maitotuotteet" ? "Juomat" : "Maitotuotteet";
  await milk.selectOption({ label: chosen });

  await expect(milk.locator("option:checked")).toHaveText(chosen);
  // The line name is an input since line editing (line-editing PC12).
  const milkRow = page
    .getByRole("table", { name: "Kuittirivit" })
    .getByRole("row")
    .filter({ has: page.getByRole("textbox", { name: "Tuote: Maito" }) });
  await expect(milkRow.getByText("ehdotus")).toHaveCount(0);
  await expect(page.getByRole("main").getByRole("status")).toHaveCount(0);

  await page.getByRole("button", { name: "Vahvista" }).click();
  await expect(page.getByText("Vahvistettu")).toBeVisible();

  await page.getByRole("link", { name: "Takaisin kuittilistaan" }).click();
  const firstRow = page
    .getByRole("table", { name: "Kuittilista" })
    .getByRole("row")
    .filter({ has: page.getByRole("link", { name: "5.10.2026" }) })
    .first();
  await expect(firstRow).toContainText("Vahvistettu");

  await navigation.getByRole("link", { name: "Tuotteet" }).click();
  const productRow = page
    .getByRole("table", { name: "Tuotelista" })
    .getByRole("row")
    .filter({ has: page.getByText("Maito", { exact: true }) });
  await expect(productRow).toContainText(chosen);
});

test("line-editing AC36: edit lines and the total of an imported receipt", async ({ page }) => {
  await writeFile(
    join(importDir, `kuitti-${RUN}_muokkaus.jpg`),
    Buffer.concat([SYNTHETIC_JPEG, Buffer.from(" edit")]),
  );
  await page.goto("/tuonti");
  await page.getByRole("button", { name: "Tuo kuitit" }).click();
  await expect(
    page.getByRole("region", { name: "Edellinen tuonti" }).getByText("Tuotu: 1"),
  ).toBeVisible();

  await page
    .getByRole("navigation", { name: "Päävalikko" })
    .getByRole("link", { name: "Kuitit" })
    .click();
  // Same-date receipts list the newest import first, so the first one is this run's.
  await page
    .getByRole("table", { name: "Kuittilista" })
    .getByRole("link", { name: "5.10.2026" })
    .first()
    .click();
  await expect(page.getByRole("heading", { name: "Kuitti", exact: true })).toBeVisible();

  const sodaAmount = page.getByRole("textbox", { name: "Summa: Limu" });
  await sodaAmount.fill("2,00");
  await sodaAmount.press("Tab");
  await expect(page.getByText("Rivien summa 3,25 €", { exact: true })).toBeVisible();

  const form = page.getByRole("form", { name: "Uusi rivi" });
  await form.getByLabel("Tuote").fill("E2E-pantti");
  await form.getByLabel("Summa").fill("-0,40");
  await form.getByLabel("Pantinpalautus").check();
  await form.getByRole("button", { name: "Lisää rivi" }).click();
  await expect(page.getByRole("textbox", { name: "Tuote: E2E-pantti" })).toBeVisible();

  const total = page.getByLabel("Loppusumma");
  await total.fill("2,85");
  await total.press("Enter");
  const milkName = page.getByRole("textbox", { name: "Tuote: Maito" });
  await milkName.fill("E2E-maito");
  await milkName.press("Enter");
  await expect(page.getByRole("textbox", { name: "Tuote: E2E-maito" })).toBeVisible();
  await expect(page.getByRole("main").getByRole("status")).toHaveCount(0);

  await page.reload();

  const lines = page.getByRole("table", { name: "Kuittirivit" });
  const names = lines.getByRole("textbox", { name: /^Tuote: / });
  await expect(names).toHaveCount(3);
  for (const [index, name] of ["E2E-maito", "Limu", "E2E-pantti"].entries()) {
    await expect(names.nth(index)).toHaveValue(name);
  }
  await expect(page.getByRole("textbox", { name: "Summa: E2E-maito" })).toHaveValue("1,25");
  await expect(page.getByRole("textbox", { name: "Summa: Limu" })).toHaveValue("2,00");
  await expect(page.getByRole("textbox", { name: "Summa: E2E-pantti" })).toHaveValue("-0,40");
  await expect(page.getByRole("checkbox", { name: "Pantinpalautus: E2E-pantti" })).toBeChecked();
  await expect(page.getByText("Rivien summa 2,85 €", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Loppusumma")).toHaveValue("2,85");
  await expect(page.getByRole("main").getByRole("status")).toHaveCount(0);
  await expect(page.getByText("Tarkistamaton")).toBeVisible();
});

const OCTOBER_TOTALS = "/yhteenveto?unit=month&from=2026-10&to=2026-10";

/** Cents of a money text: `1234,56 €` → 123456. */
function cents(text: string): number {
  return Number(text.replace(" €", "").replace(",", ""));
}

/**
 * The October 2026 total of Leivät in the Kuukaudet table, 0 when it has no row. The E2E
 * database keeps earlier tests' receipts, so the test compares totals instead of fixing them.
 */
async function octoberBread(page: Page): Promise<number> {
  await page.goto(OCTOBER_TOTALS);
  const months = page.getByRole("table", { name: "Kuukaudet" });
  await expect(months.or(page.getByText("Ei ostoksia valitulla jaksolla."))).toBeVisible();
  const expand = months.getByRole("button", { name: "Näytä kategoriat: Ruoka" });
  if ((await expand.count()) === 0) {
    return 0;
  }
  await expand.click();
  const bread = months
    .getByRole("row")
    .filter({ has: page.getByRole("rowheader", { name: "Leivät" }) });
  if ((await bread.count()) === 0) {
    return 0;
  }
  return cents((await bread.getByRole("cell").first().textContent()) ?? "");
}

test("totals AC14, AC11: a corrected line shows in the month's totals", async ({ page }) => {
  await writeFile(
    join(importDir, `kuitti-${RUN}_yhteenveto.jpg`),
    Buffer.concat([SYNTHETIC_JPEG, Buffer.from(" totals")]),
  );
  await page.goto("/tuonti");
  await page.getByRole("button", { name: "Tuo kuitit" }).click();
  await expect(
    page.getByRole("region", { name: "Edellinen tuonti" }).getByText("Tuotu: 1"),
  ).toBeVisible();
  const before = await octoberBread(page);
  await expect(page).toHaveURL(OCTOBER_TOTALS);
  await expect(page.getByRole("heading", { name: "Yhteenveto" })).toBeVisible();

  await page
    .getByRole("navigation", { name: "Päävalikko" })
    .getByRole("link", { name: "Kuitit" })
    .click();
  // Same-date receipts list the newest import first, so the first one is this run's.
  await page
    .getByRole("table", { name: "Kuittilista" })
    .getByRole("link", { name: "5.10.2026" })
    .first()
    .click();
  // A product name of its own, so no earlier line follows the category choice (FR-36).
  const name = `E2E-leipä-${RUN}`;
  const form = page.getByRole("form", { name: "Uusi rivi" });
  await form.getByLabel("Tuote").fill(name);
  await form.getByLabel("Summa").fill("3,10");
  await form.getByRole("button", { name: "Lisää rivi" }).click();
  const category = page.getByRole("combobox", { name: `Kategoria: ${name}` });
  await expect(category).toBeEnabled();
  await category.selectOption({ label: "Leivät" });
  await expect(category.locator("option:checked")).toHaveText("Leivät");

  expect(await octoberBread(page)).toBe(before + 310);
});

/** Click an export link and return the download's name and text (without the BOM). */
async function download(page: Page, link: string): Promise<{ name: string; text: string }> {
  const started = page.waitForEvent("download");
  await page.getByRole("link", { name: link }).click();
  const file = await started;
  const bytes = await readFile(await file.path());
  expect([...bytes.subarray(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
  return { name: file.suggestedFilename(), text: bytes.subarray(3).toString("utf-8") };
}

const TOTALS_HEADER = "Jakso;Alkaa;Päättyy;Osittainen;Ryhmä;Kategoria;Summa\r\n";

test("date range AC14, AC20: totals and export of a date range", async ({ page }) => {
  await writeFile(
    join(importDir, `kuitti-${RUN}_aikavali.jpg`),
    Buffer.concat([SYNTHETIC_JPEG, Buffer.from(" range")]),
  );
  await page.goto("/tuonti");
  await page.getByRole("button", { name: "Tuo kuitit" }).click();
  await expect(
    page.getByRole("region", { name: "Edellinen tuonti" }).getByText("Tuotu: 1"),
  ).toBeVisible();
  await page.goto("/yhteenveto");

  await page.getByRole("combobox", { name: "Jakso" }).selectOption({ label: "Aikaväli" });
  await expect(page.getByLabel("Alkaen", { exact: true })).not.toBeEditable();
  // Set through the calendar's input, so this journey does not depend on its window.
  const calendars = page.locator('input[type="date"]');
  await calendars.nth(0).fill("2026-10-03");
  await expect(page).toHaveURL(/from=2026-10-03/);
  await calendars.nth(1).fill("2026-10-07");
  await expect(page).toHaveURL(/\?unit=range&from=2026-10-03&to=2026-10-07$/);
  await page.reload();

  await expect(page.getByRole("combobox", { name: "Jakso" })).toHaveValue("range");
  await expect(page.getByLabel("Alkaen", { exact: true })).toHaveValue("03.10.2026");
  await expect(page.getByRole("table", { name: "Viikot" })).toContainText(
    "vk 41/2026 (osittainen) 5.10.–7.10.2026",
  );
  const weeks = await download(page, "Vie viikkosummat (CSV)");
  expect(weeks.name).toBe("summat_viikot_2026-10-03_2026-10-07.csv");
  expect(weeks.text.startsWith(TOTALS_HEADER)).toBe(true);
  expect(weeks.text).toContain("2026-W41;05.10.2026;07.10.2026;kyllä;");
});

test("export AC1, AC2, AC16, AC13: download the CSV files of a month", async ({ page }) => {
  await writeFile(
    join(importDir, `kuitti-${RUN}_vienti.jpg`),
    Buffer.concat([SYNTHETIC_JPEG, Buffer.from(" export")]),
  );
  await page.goto("/tuonti");
  await page.getByRole("button", { name: "Tuo kuitit" }).click();
  await expect(
    page.getByRole("region", { name: "Edellinen tuonti" }).getByText("Tuotu: 1"),
  ).toBeVisible();
  await page.goto(OCTOBER_TOTALS);
  await expect(page.getByRole("link", { name: "Vie rivit (CSV)" })).toBeVisible();

  const weeks = await download(page, "Vie viikkosummat (CSV)");
  const months = await download(page, "Vie kuukausisummat (CSV)");
  const lines = await download(page, "Vie rivit (CSV)");

  expect(weeks.name).toBe("summat_viikot_2026-10_2026-10.csv");
  expect(months.name).toBe("summat_kuukaudet_2026-10_2026-10.csv");
  expect(lines.name).toBe("kuittirivit_2026-10_2026-10.csv");
  expect(weeks.text.startsWith(TOTALS_HEADER)).toBe(true);
  expect(weeks.text).toContain("\r\n2026-W41;05.10.2026;11.10.2026;ei;");
  expect(weeks.text).not.toContain("\r\n2026-10;");
  expect(months.text.startsWith(TOTALS_HEADER)).toBe(true);
  expect(months.text).toContain("\r\n2026-10;01.10.2026;31.10.2026;ei;");
  expect(months.text).not.toContain("2026-W");
  expect(lines.text).toContain(";Maito;1,25;");
  expect(lines.text).toContain(";Limu;2,24;");
});

test("date-field AC6, AC7, AC16, AC17: the real calendar picks only a chosen day", async ({
  page,
}) => {
  const address = "/yhteenveto?unit=range&from=2026-10-15&to=2026-11-14";
  // The browser's calendar window is not in the page, so nothing shows that it has opened.
  const OPENING_MS = 500;
  await page.goto(address);
  const from = page.getByLabel("Alkaen", { exact: true });
  await expect(from).toHaveValue("15.10.2026");
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/totals")) {
      requests.push(request.url());
    }
  });

  await page.getByRole("button", { name: "Avaa kalenteri: Alkaen" }).focus();
  await page.keyboard.press("Enter");
  await page.waitForTimeout(OPENING_MS);
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(OPENING_MS);

  expect(requests).toEqual([]);
  expect(page.url()).toContain(address);
  await expect(from).toHaveValue("15.10.2026");

  await from.click();
  await page.waitForTimeout(OPENING_MS);
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL(/from=2026-10-16&to=2026-11-14$/);
  await expect(from).toHaveValue("16.10.2026");
  expect(requests).toHaveLength(1);
});
