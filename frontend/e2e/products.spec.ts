import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

// The journeys share one fresh database per run, so each uses its own names and none
// depends on another having run. The page is in two columns (products two columns spec);
// the helpers below changed from the category panel's rows to the tree and the tools of
// the selected item (G7 record), the steps and expectations stay.

const RUN = Date.now();

function column(page: Page): Locator {
  return page.getByRole("region", { name: "Kategoriat" });
}

/** The selectable tree button of a group or category, or of "Kaikki tuotteet". */
function treeItem(page: Page, name: string): Locator {
  return column(page).getByRole("button", { name, exact: true });
}

/** The count beside a tree item. */
function countOf(page: Page, name: string): Locator {
  return treeItem(page, name).locator("xpath=..").locator(":scope > [data-count]");
}

/** A category's tree item inside its group's list. */
function inGroup(page: Page, group: string, name: string): Locator {
  return column(page).locator(
    `xpath=//li[button[@aria-pressed][normalize-space()="${group}"]]//li/button[normalize-space()="${name}"]`,
  );
}

/** The product column, named by the selected item. */
function productColumn(page: Page, name: string): Locator {
  return page.getByRole("region", { name, exact: true });
}

/**
 * The tools of the selected item. Scoped to them, because the product column also holds
 * the product rows (the previous selection's rows until the new list loads) and the new
 * product form's error.
 */
function tools(page: Page, name: string): Locator {
  return productColumn(page, name).locator(".category-tools");
}

function productRow(page: Page, name: string): Locator {
  return page
    .getByRole("table", { name: "Tuotelista" })
    .getByRole("row")
    .filter({ has: page.getByText(name, { exact: true }) });
}

async function select(page: Page, name: string): Promise<void> {
  await treeItem(page, name).click();
  await expect(treeItem(page, name)).toHaveAttribute("aria-pressed", "true");
}

async function addProduct(page: Page, name: string, category: string): Promise<void> {
  const form = page.getByRole("form", { name: "Uusi tuote" });
  await form.getByRole("textbox", { name: "Tuotteen nimi" }).fill(name);
  await form.getByRole("combobox", { name: "Kategoria" }).selectOption({ label: category });
  await form.getByRole("button", { name: "Lisää" }).click();
  await expect(productRow(page, name)).toBeVisible();
}

/** Deletes the selected item with its tools; they come before the product rows. */
async function deleteSelected(page: Page, name: string): Promise<void> {
  await tools(page, name).getByRole("button", { name: "Poista" }).first().click();
  await tools(page, name).getByRole("button", { name: "Poista" }).first().click();
}

async function noViolations(page: Page): Promise<void> {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(result.violations).toEqual([]);
}

test("AC2, AC8, AC10, AC14, AC15, AC18: manage groups, categories and products through the tree", async ({
  page,
}) => {
  await page.goto("/");

  await column(page).getByRole("button", { name: "Uusi ryhmä" }).click();
  const groupForm = page.getByRole("form", { name: "Uusi ryhmä" });
  await expect(groupForm.getByRole("textbox", { name: "Ryhmän nimi" })).toBeFocused();
  await groupForm.getByRole("textbox", { name: "Ryhmän nimi" }).fill("Testiryhmä");
  await groupForm.getByRole("button", { name: "Lisää" }).click();
  await expect(treeItem(page, "Testiryhmä")).toBeVisible();

  await column(page).getByRole("button", { name: "Uusi kategoria" }).click();
  const categoryForm = page.getByRole("form", { name: "Uusi kategoria" });
  await categoryForm.getByRole("textbox", { name: "Kategorian nimi" }).fill("Testikategoria");
  await categoryForm.getByRole("combobox", { name: "Ryhmä" }).selectOption({ label: "Testiryhmä" });
  await categoryForm.getByRole("button", { name: "Lisää" }).click();
  await expect(inGroup(page, "Testiryhmä", "Testikategoria")).toBeVisible();

  await select(page, "Testikategoria");
  await expect(
    productColumn(page, "Testikategoria").getByRole("heading", { name: "Testikategoria" }),
  ).toBeVisible();
  const productForm = page.getByRole("form", { name: "Uusi tuote" });
  await expect(
    productForm.getByRole("combobox", { name: "Kategoria" }).locator("option:checked"),
  ).toHaveText("Testikategoria");
  await productForm.getByRole("textbox", { name: "Tuotteen nimi" }).fill("Testituote");
  await productForm.getByRole("button", { name: "Lisää" }).click();
  await expect(productRow(page, "Testituote")).toBeVisible();
  await expect(countOf(page, "Testikategoria")).toHaveText("1 tuote");

  await productRow(page, "Testituote")
    .getByRole("combobox", { name: "Kategoria" })
    .selectOption({ label: "Juomat" });
  await expect(countOf(page, "Testikategoria")).toHaveText("0 tuotetta");
  await expect(productRow(page, "Testituote")).toHaveCount(0);

  await select(page, "Kaikki tuotteet");
  const row = productRow(page, "Testituote");
  await row.getByRole("button", { name: "Poista" }).click();
  await row.getByRole("button", { name: "Poista" }).click();
  await expect(productRow(page, "Testituote")).toHaveCount(0);

  await select(page, "Testikategoria");
  const own = tools(page, "Testikategoria");
  await own.getByRole("button", { name: "Nimeä" }).click();
  await own.getByRole("textbox", { name: "Kategorian nimi" }).fill("Testikategoria 2");
  await own.getByRole("button", { name: "Tallenna" }).click();
  await expect(treeItem(page, "Testikategoria 2")).toHaveAttribute("aria-pressed", "true");

  await deleteSelected(page, "Testikategoria 2");
  await expect(treeItem(page, "Testikategoria 2")).toHaveCount(0);
  await expect(treeItem(page, "Kaikki tuotteet")).toHaveAttribute("aria-pressed", "true");
  await select(page, "Testiryhmä");
  await deleteSelected(page, "Testiryhmä");
  await expect(treeItem(page, "Testiryhmä")).toHaveCount(0);
});

test("AC13: a used category and a group with categories are not deleted", async ({ page }) => {
  await page.goto("/");
  await addProduct(page, "Suojattu tuote", "Juomat");

  await select(page, "Juomat");
  await deleteSelected(page, "Juomat");
  await expect(tools(page, "Juomat").getByRole("alert")).toContainText(/Kategoriaa käyttää \d+/);

  await select(page, "Auto");
  await deleteSelected(page, "Auto");
  await expect(tools(page, "Auto").getByRole("alert")).toContainText("Ryhmässä on 3 kategoriaa.");
  await expect(treeItem(page, "Juomat")).toBeVisible();
  await expect(treeItem(page, "Auto")).toHaveAttribute("aria-pressed", "true");
});

test("AC4, AC31: the app opens on Tuotteet and search finds a product", async ({ page }) => {
  await page.goto("/");
  const navigation = page.getByRole("navigation", { name: "Päävalikko" });
  await expect(navigation.getByRole("link", { name: "Tuotteet" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  // `exact`: the product column heading "Kaikki tuotteet" contains the word (G7 record).
  await expect(
    page.getByRole("main").getByRole("heading", { name: "Tuotteet", exact: true }),
  ).toBeVisible();

  await addProduct(page, "Hakutesti Alfa", "Muut");
  await addProduct(page, "Hakutesti Beeta", "Muut");
  await page.getByRole("searchbox", { name: "Hae" }).fill("ALFA");

  await expect(productRow(page, "Hakutesti Beeta")).toHaveCount(0);
  await expect(productRow(page, "Hakutesti Alfa")).toBeVisible();
});

test("AC21, AC22: two columns on a wide window, one on a narrow window", async ({
  page,
  request,
}) => {
  const categories = (await (await request.get("/api/categories")).json()) as {
    id: number;
    name: string;
  }[];
  const muut = categories.find((item) => item.name === "Muut");
  expect(muut).toBeDefined();
  for (let index = 0; index < 60; index++) {
    const response = await request.post("/api/products", {
      data: { name: `Asettelu ${RUN} ${index}`, category_id: muut?.id },
    });
    expect(response.status()).toBe(201);
  }

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await expect(productRow(page, `Asettelu ${RUN} 59`)).toBeVisible();
  const tree = await column(page).boundingBox();
  const products = await productColumn(page, "Kaikki tuotteet").boundingBox();
  expect(tree && products).toBeTruthy();
  if (tree && products) {
    expect(tree.x + tree.width).toBeLessThan(products.x);
    expect(Math.abs(tree.y - products.y)).toBeLessThanOrEqual(1);
  }
  await page.evaluate(() => window.scrollBy(0, 400));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(400);
  const all = await treeItem(page, "Kaikki tuotteet").boundingBox();
  expect(all).not.toBeNull();
  if (all) {
    expect(all.y).toBeGreaterThanOrEqual(0);
    expect(all.y + all.height).toBeLessThanOrEqual(800);
  }

  await page.setViewportSize({ width: 800, height: 800 });
  await page.evaluate(() => window.scrollTo(0, 0));
  const narrowTree = await column(page).boundingBox();
  const narrowProducts = await productColumn(page, "Kaikki tuotteet").boundingBox();
  expect(narrowTree && narrowProducts).toBeTruthy();
  if (narrowTree && narrowProducts) {
    expect(narrowTree.y + narrowTree.height).toBeLessThanOrEqual(narrowProducts.y);
  }
  const widths = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client);
});

test("AC23: the page passes axe in its states, and Tab follows the tree", async ({ page }) => {
  await page.goto("/");
  await expect(treeItem(page, "Ruoka")).toBeVisible();

  const navigation = page.getByRole("navigation", { name: "Päävalikko" });
  await navigation.getByRole("link").last().focus();
  const focusedNames: string[] = [];
  for (let step = 0; step < 60; step++) {
    await page.keyboard.press("Tab");
    const name = await page.evaluate(() => {
      const element = document.activeElement as HTMLElement | null;
      return element?.getAttribute("aria-label") ?? element?.textContent?.trim() ?? "";
    });
    focusedNames.push(name);
    if (name === "Hae") {
      break;
    }
  }
  expect(focusedNames.slice(0, 6)).toEqual([
    "Uusi ryhmä",
    "Uusi kategoria",
    "Kaikki tuotteet",
    "Piilota kategoriat: Auto",
    "Auto",
    "Autohuolto",
  ]);
  expect(focusedNames.at(-1)).toBe("Hae");

  await noViolations(page);
  await select(page, "Maitotuotteet");
  await noViolations(page);
  await column(page).getByRole("button", { name: "Piilota kategoriat: Ruoka" }).click();
  await expect(
    column(page).getByRole("button", { name: "Näytä kategoriat: Ruoka" }),
  ).toHaveAttribute("aria-expanded", "false");
  await noViolations(page);
  await column(page).getByRole("button", { name: "Uusi ryhmä" }).click();
  await expect(page.getByRole("form", { name: "Uusi ryhmä" })).toBeVisible();
  await noViolations(page);
});

test("AC24: the page uses the window's width", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 900 });
  await page.goto("/");
  await expect(treeItem(page, "Ruoka")).toBeVisible();

  const categoryBox = await column(page).boundingBox();
  const productBox = await productColumn(page, "Kaikki tuotteet").boundingBox();
  const tableBox = await page.getByRole("table", { name: "Tuotelista" }).boundingBox();
  const headingBox = await page
    .getByRole("main")
    .getByRole("heading", { name: "Tuotteet", exact: true })
    .boundingBox();
  const widths = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));

  expect(categoryBox).not.toBeNull();
  expect(productBox).not.toBeNull();
  expect(tableBox).not.toBeNull();
  expect(headingBox).not.toBeNull();
  if (categoryBox && productBox && tableBox && headingBox) {
    expect(Math.abs(categoryBox.x - 24)).toBeLessThanOrEqual(1);
    expect(Math.abs(productBox.width - 768)).toBeLessThanOrEqual(1);
    // `100vw` includes the vertical scroll bar, so the gap is measured from the window.
    expect(1920 - (productBox.x + productBox.width)).toBeLessThanOrEqual(24);
    expect(Math.abs(productBox.x - (categoryBox.x + categoryBox.width) - 16)).toBeLessThanOrEqual(
      1,
    );
    expect(Math.abs(tableBox.width - productBox.width)).toBeLessThanOrEqual(1);
    expect(Math.abs(headingBox.x - categoryBox.x)).toBeLessThanOrEqual(1);
  }
  expect(widths.scroll).toBeLessThanOrEqual(widths.client);

  // The space between a count and the category column's scroll bar (or its right edge).
  const countGap = await countOf(page, "Ruoka").evaluate((count) => {
    const columnElement = count.closest("section") as HTMLElement;
    const inner = columnElement.getBoundingClientRect().left + columnElement.clientLeft;
    return inner + columnElement.clientWidth - count.getBoundingClientRect().right;
  });
  expect(Math.abs(countGap - 16)).toBeLessThanOrEqual(1);

  await page.setViewportSize({ width: 1000, height: 900 });
  const narrowBox = await column(page).boundingBox();
  expect(narrowBox).not.toBeNull();
  expect(Math.abs((narrowBox?.width ?? 0) - 352)).toBeLessThanOrEqual(1);
});
