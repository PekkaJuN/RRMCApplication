import { readdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { expect, test } from "@playwright/test";

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
