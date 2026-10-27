import { expect, test, type Locator, type Page } from "@playwright/test";

// The journeys share one fresh database per run, so each uses its own names and none
// depends on another having run.

/** The list item of a group or category whose own name is `name` (not a child's). */
function entry(page: Page, name: string): Locator {
  return page.locator(`xpath=//li[span[@data-name][normalize-space()="${name}"]]`);
}

function productRow(page: Page, name: string): Locator {
  return page
    .getByRole("table", { name: "Tuotelista" })
    .getByRole("row")
    .filter({ has: page.getByText(name, { exact: true }) });
}

async function addProduct(page: Page, name: string, category: string): Promise<void> {
  const form = page.getByRole("form", { name: "Uusi tuote" });
  await form.getByRole("textbox", { name: "Tuotteen nimi" }).fill(name);
  await form.getByRole("combobox", { name: "Kategoria" }).selectOption({ label: category });
  await form.getByRole("button", { name: "Lisää" }).click();
  await expect(productRow(page, name)).toBeVisible();
}

async function deleteEntry(item: Locator): Promise<void> {
  // The item's own delete button comes before those of its categories.
  await item.getByRole("button", { name: "Poista" }).first().click();
  await item.getByRole("button", { name: "Poista" }).first().click();
}

test("AC8, AC15, AC16, AC20, AC22: manage groups, categories and products", async ({ page }) => {
  await page.goto("/");

  const groupForm = page.getByRole("form", { name: "Uusi ryhmä" });
  await groupForm.getByRole("textbox", { name: "Ryhmän nimi" }).fill("Testiryhmä");
  await groupForm.getByRole("button", { name: "Lisää" }).click();
  await expect(entry(page, "Testiryhmä")).toBeVisible();

  const categoryForm = page.getByRole("form", { name: "Uusi kategoria" });
  await categoryForm.getByRole("textbox", { name: "Kategorian nimi" }).fill("Testikategoria");
  await categoryForm.getByRole("combobox", { name: "Ryhmä" }).selectOption({ label: "Testiryhmä" });
  await categoryForm.getByRole("button", { name: "Lisää" }).click();
  await expect(entry(page, "Testiryhmä").locator(entry(page, "Testikategoria"))).toBeVisible();

  await addProduct(page, "Testituote", "Testikategoria");
  await expect(entry(page, "Testikategoria")).toContainText("1 tuote");

  await productRow(page, "Testituote")
    .getByRole("combobox", { name: "Kategoria" })
    .selectOption({ label: "Juomat" });
  await expect(entry(page, "Testikategoria")).toContainText("0 tuotetta");

  await deleteEntry(productRow(page, "Testituote"));
  await expect(productRow(page, "Testituote")).toHaveCount(0);

  await deleteEntry(entry(page, "Testikategoria"));
  await expect(entry(page, "Testikategoria")).toHaveCount(0);
  await deleteEntry(entry(page, "Testiryhmä"));
  await expect(entry(page, "Testiryhmä")).toHaveCount(0);
});

test("AC13, AC14: a used category and a group with categories are not deleted", async ({
  page,
}) => {
  await page.goto("/");
  await addProduct(page, "Suojattu tuote", "Juomat");

  await deleteEntry(entry(page, "Juomat"));
  await expect(entry(page, "Juomat").getByRole("alert")).toContainText(/Kategoriaa käyttää \d+/);

  await deleteEntry(entry(page, "Auto"));
  await expect(entry(page, "Auto").getByRole("alert").first()).toContainText(
    "Ryhmässä on 3 kategoriaa.",
  );
  await expect(entry(page, "Juomat")).toBeVisible();
  await expect(entry(page, "Auto")).toBeVisible();
});

test("AC23, AC31: the app opens on Tuotteet and search finds a product", async ({ page }) => {
  await page.goto("/");
  const navigation = page.getByRole("navigation", { name: "Päävalikko" });
  await expect(navigation.getByRole("link", { name: "Tuotteet" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(page.getByRole("main").getByRole("heading", { name: "Tuotteet" })).toBeVisible();

  await addProduct(page, "Hakutesti Alfa", "Muut");
  await addProduct(page, "Hakutesti Beeta", "Muut");
  await page.getByRole("searchbox", { name: "Hae" }).fill("ALFA");

  await expect(productRow(page, "Hakutesti Beeta")).toHaveCount(0);
  await expect(productRow(page, "Hakutesti Alfa")).toBeVisible();
});
