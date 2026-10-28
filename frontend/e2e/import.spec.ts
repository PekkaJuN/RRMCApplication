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
