import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { expect, test, type Browser, type Locator, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { syntheticPng } from "./synthetic";

// Visual style and accessibility (specs/features/styling.md). Runs in the `style` project,
// after the other specs, on a receipt it imports itself (styling spec P6).

const importDir = process.env.E2E_IMPORT_DIR ?? "";
const RUN = Date.now();
const ORIGIN = "http://127.0.0.1:5173";
const OCTOBER_TOTALS = "/yhteenveto?unit=month&from=2026-10&to=2026-10";

/** The address of the receipt this file imports, set by `beforeAll`. */
let receiptPath = "";

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  expect(importDir, "E2E_IMPORT_DIR is set by compose.yaml").not.toBe("");
  await writeFile(join(importDir, `kuitti-${RUN}_tyyli.png`), syntheticPng(`style ${RUN}`));
  const page = await browser.newPage();
  await page.goto("/tuonti");
  await page.getByRole("button", { name: "Tuo kuitit" }).click();
  await expect(
    page.getByRole("region", { name: "Edellinen tuonti" }).getByText("Tuotu: 1"),
  ).toBeVisible();
  await page.goto("/kuitit");
  // Same-date receipts list the newest import first, so the first one is this run's.
  await page
    .getByRole("table", { name: "Kuittilista" })
    .getByRole("link", { name: "5.10.2026" })
    .first()
    .click();
  await expect(page.getByRole("table", { name: "Kuittirivit" })).toBeVisible();
  receiptPath = new URL(page.url()).pathname;
  await page.close();
});

/** Open the receipt page and wait for its lines and image. */
async function openReceipt(page: Page): Promise<void> {
  await page.goto(receiptPath);
  await expect(page.getByRole("table", { name: "Kuittirivit" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Kuitin kuva" })).toBeVisible();
}

test("styling setup: the imported receipt shows its image", async ({ page }) => {
  await openReceipt(page);

  const image = page.getByRole("img", { name: "Kuitin kuva" });
  expect(await image.evaluate((element) => (element as HTMLImageElement).naturalWidth)).toBe(1);
});

/** The computed value of a CSS property of the element. */
async function css(locator: Locator, property: string): Promise<string> {
  return locator.evaluate(
    (element, name) => getComputedStyle(element).getPropertyValue(name),
    property,
  );
}

/** Open Yhteenveto for October 2026 with the group Ruoka expanded in both tables. */
async function openOctoberTotals(page: Page, address = OCTOBER_TOTALS): Promise<void> {
  await page.goto(address);
  const months = page.getByRole("table", { name: "Kuukaudet" });
  await months.getByRole("button", { name: "Näytä kategoriat: Ruoka" }).click();
  await expect(months.getByRole("rowheader", { name: "Leivät" })).toBeVisible();
}

/** The pages of the styling spec's ACs, each with how to open it and wait for it. */
const PAGES: { name: string; open: (page: Page) => Promise<void> }[] = [
  {
    name: "Tuotteet",
    open: async (page) => {
      await page.goto("/");
      await expect(page.getByRole("table", { name: "Tuotelista" })).toBeVisible();
    },
  },
  {
    name: "Tuonti",
    open: async (page) => {
      await page.goto("/tuonti");
      await expect(page.getByRole("button", { name: "Tuo kuitit" })).toBeVisible();
    },
  },
  {
    name: "Kuitit",
    open: async (page) => {
      await page.goto("/kuitit");
      await expect(page.getByRole("table", { name: "Kuittilista" })).toBeVisible();
    },
  },
  { name: "kuitti", open: openReceipt },
  { name: "Yhteenveto", open: (page) => openOctoberTotals(page) },
];

test("styling AC1, AC3: no inline style and nothing from other hosts", async ({ page }) => {
  const origins = new Set<string>();
  page.on("request", (request) => origins.add(new URL(request.url()).origin));

  for (const { name, open } of PAGES) {
    await open(page);
    expect(await page.locator("[style]").count(), name).toBe(0);
  }

  expect([...origins]).toEqual([ORIGIN]);
});

test("styling AC2: the stylesheet sets the font and the custom properties", async ({ page }) => {
  await PAGES[0]?.open(page);

  expect(await css(page.locator("body"), "font-family")).toMatch(/^system-ui/);
  expect((await css(page.locator(":root"), "--color-accent")).trim()).not.toBe("");
});

/** `--color-accent` of `:root` as the browser reports colors, e.g. `rgb(29, 78, 216)`. */
async function accent(page: Page): Promise<string> {
  const hex = (await css(page.locator(":root"), "--color-accent")).trim();
  const [r, g, b] = [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16));
  return `rgb(${r}, ${g}, ${b})`;
}

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

async function box(locator: Locator): Promise<Box> {
  const found = await locator.boundingBox();
  expect(found).not.toBeNull();
  return found ?? { x: 0, y: 0, width: 0, height: 0 };
}

test("styling AC4: the content is at most 1200 px wide and centred", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await PAGES[2]?.open(page);

  const main = await box(page.locator("main"));
  const windowWidth = await page.evaluate(() => document.documentElement.clientWidth);
  expect(Math.abs(main.width - 1200)).toBeLessThanOrEqual(1);
  expect(Math.abs(main.x - (windowWidth - main.x - main.width))).toBeLessThanOrEqual(1);
});

test("styling AC5: no sideways scrolling at 600 px; a wide table scrolls in its box", async ({
  page,
}) => {
  await page.setViewportSize({ width: 600, height: 800 });
  const nineWeeks = async (target: Page) => {
    await target.goto("/yhteenveto?unit=week&from=2026-W40&to=2026-W48");
    await expect(target.getByRole("table", { name: "Viikot" })).toBeVisible();
  };

  for (const { name, open } of [...PAGES, { name: "9 viikkoa", open: nineWeeks }]) {
    await open(page);
    const width = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(width, name).toBeLessThanOrEqual(600);
  }
  const weeksBox = page.getByRole("table", { name: "Viikot" }).locator("xpath=..");
  const [scrollWidth, clientWidth] = await weeksBox.evaluate((element) => [
    element.scrollWidth,
    element.clientWidth,
  ]);
  expect(scrollWidth).toBeGreaterThan(clientWidth ?? 0);
});

test("styling AC6: the current page is bold and underlined in the navigation", async ({ page }) => {
  await PAGES[2]?.open(page);
  const navigation = page.getByRole("navigation", { name: "Päävalikko" });

  const current = navigation.getByRole("link", { name: "Kuitit" });
  expect(await css(current, "font-weight")).toBe("700");
  expect(await css(current, "border-bottom-style")).toBe("solid");
  expect(await css(current, "border-bottom-width")).toBe("3px");
  expect(await css(current, "border-bottom-color")).toBe(await accent(page));
  for (const name of ["Tuotteet", "Tuonti", "Yhteenveto"]) {
    const other = navigation.getByRole("link", { name });
    expect(await css(other, "font-weight"), name).toBe("400");
    expect(await css(other, "border-bottom-style"), name).toBe("none");
  }
});

test("styling AC7: amounts are aligned right with tabular figures", async ({ page }) => {
  let found = 0;
  for (const { name, open } of PAGES) {
    await open(page);
    const cells = await page.evaluate(() =>
      [...document.querySelectorAll("main td, main th")]
        .filter((cell) => /^-?[0-9]+,[0-9]{2} €$/.test(cell.textContent?.trim() ?? ""))
        .map((cell) => {
          const style = getComputedStyle(cell);
          return [cell.textContent, style.textAlign, style.fontVariantNumeric];
        }),
    );
    for (const [text, align, numeric] of cells) {
      expect(align, `${name}: ${text}`).toBe("right");
      expect(numeric, `${name}: ${text}`).toContain("tabular-nums");
    }
    found += cells.length;
    for (const input of await page.getByLabel(/^Summa/).all()) {
      expect(await css(input, "text-align"), name).toBe("right");
      expect(await css(input, "font-variant-numeric"), name).toContain("tabular-nums");
      found += 1;
    }
  }
  expect(found).toBeGreaterThan(0);
});

/** The left edge of the first text node in the element that contains `text`. */
async function textLeft(cell: Locator, text: string): Promise<number> {
  return cell.evaluate((element, wanted) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (node.textContent?.includes(wanted)) {
        const range = document.createRange();
        range.selectNodeContents(node);
        return range.getBoundingClientRect().left;
      }
    }
    return Number.NaN;
  }, text);
}

test("styling AC8: group and total rows are bold and categories indented", async ({ page }) => {
  await openOctoberTotals(page);
  const months = page.getByRole("table", { name: "Kuukaudet" });
  const ruoka = months.getByRole("rowheader", { name: /Ruoka/ });
  const total = months.getByRole("rowheader", { name: "Yhteensä" });
  const leivat = months.getByRole("rowheader", { name: "Leivät" });

  expect(await css(ruoka, "font-weight")).toBe("700");
  expect(await css(total, "font-weight")).toBe("700");
  expect(
    (await textLeft(leivat, "Leivät")) - (await textLeft(ruoka, "Ruoka")),
  ).toBeGreaterThanOrEqual(16);
});

test("styling AC9, AC10: one button style; a disabled button looks disabled", async ({ page }) => {
  const properties = [
    "border-top-width",
    "border-top-left-radius",
    "padding-left",
    "padding-top",
    "background-color",
  ];
  await page.goto("/tuonti");
  const importButton = page.getByRole("button", { name: "Tuo kuitit" });
  const buttonStyle = await Promise.all(properties.map((name) => css(importButton, name)));

  expect(await css(importButton, "cursor")).toBe("pointer");
  expect(await css(importButton, "opacity")).toBe("1");
  await importButton.evaluate((element) => {
    (element as HTMLButtonElement).disabled = true;
  });
  expect(await css(importButton, "cursor")).toBe("not-allowed");
  expect(Number(await css(importButton, "opacity"))).toBeLessThan(1);
  await importButton.evaluate((element) => {
    (element as HTMLButtonElement).disabled = false;
  });
  expect(await css(importButton, "cursor")).toBe("pointer");

  await page.goto(OCTOBER_TOTALS);
  const link = page.getByRole("link", { name: "Vie rivit (CSV)" });
  await expect(link).toBeVisible();
  expect(await Promise.all(properties.map((name) => css(link, name)))).toEqual(buttonStyle);
  expect(buttonStyle[4]).not.toBe("rgba(0, 0, 0, 0)");
});

test("styling AC11, AC12: error and notice paragraphs", async ({ page }) => {
  await page.goto("/yhteenveto?unit=month&from=2026-11&to=2026-10");
  const error = page.getByRole("alert");
  await expect(error).toHaveText("Jakso on virheellinen.");
  const body = await css(page.locator("body"), "background-color");
  const errorBackground = await css(error, "background-color");
  expect(errorBackground).not.toBe(body);
  expect(await css(error, "border-left-style")).toBe("solid");
  expect(await css(error, "border-left-width")).toBe("4px");

  await page.goto(OCTOBER_TOTALS);
  const notice = page
    .getByRole("main")
    .getByRole("status")
    .filter({ hasText: /^Tarkistamattomia/ });
  await expect(notice).toBeVisible();
  const noticeBackground = await css(notice, "background-color");
  expect(noticeBackground).not.toBe(body);
  expect(noticeBackground).not.toBe(errorBackground);
  expect(await css(notice, "border-left-style")).toBe("solid");
  expect(await css(notice, "border-left-width")).toBe("4px");
});

/** Press Tab until `target` has the focus (at most 30 times). */
async function tabTo(page: Page, target: Locator): Promise<void> {
  for (let presses = 0; presses < 30; presses += 1) {
    if (await target.evaluate((element) => element === document.activeElement)) {
      return;
    }
    await page.keyboard.press("Tab");
  }
  throw new Error("Tab did not reach the element");
}

test("styling AC13: keyboard focus shows an outline", async ({ page }) => {
  const targets: [string, Locator][] = [
    [
      "/",
      page.getByRole("navigation", { name: "Päävalikko" }).getByRole("link", { name: "Tuonti" }),
    ],
    ["/tuonti", page.getByRole("button", { name: "Tuo kuitit" })],
  ];
  for (const [address, target] of targets) {
    await page.goto(address);
    await expect(target).toBeVisible();
    await tabTo(page, target);
    expect(await css(target, "outline-style"), address).toBe("solid");
    expect(parseFloat(await css(target, "outline-width")), address).toBeGreaterThanOrEqual(2);
    expect(await css(target, "outline-color"), address).toBe(await accent(page));
  }
});

test("styling AC14, AC15: the receipt image beside the lines, or above them", async ({ page }) => {
  const image = page.getByRole("img", { name: "Kuitin kuva" });
  const lines = page.getByRole("table", { name: "Kuittirivit" });

  await page.setViewportSize({ width: 1280, height: 800 });
  await openReceipt(page);
  const wideImage = await box(image);
  const wideLines = await box(lines);
  expect(wideImage.x + wideImage.width).toBeLessThan(wideLines.x);
  expect(Math.abs(wideImage.y - wideLines.y)).toBeLessThanOrEqual(1);

  await page.setViewportSize({ width: 800, height: 800 });
  await openReceipt(page);
  const narrowImage = await box(image);
  const narrowLines = await box(lines);
  expect(narrowImage.y + narrowImage.height).toBeLessThanOrEqual(narrowLines.y);
});

// Regression (docs/learnings.md 2026-11-02): the line table scrolled sideways beside the
// image, so each line's delete button was out of sight.
test("styling AC14: every line's delete button is in sight beside the image", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await openReceipt(page);
  const lines = page.getByRole("table", { name: "Kuittirivit" });
  const tableBox = page.locator(".receipt-lines .table-box");

  const overflow = await tableBox.evaluate((element) => element.scrollWidth - element.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  const visible = await box(tableBox);
  const buttons = lines.getByRole("button", { name: "Poista" });
  expect(await buttons.count()).toBeGreaterThan(0);
  for (const button of await buttons.all()) {
    const target = await box(button);
    expect(target.x + target.width).toBeLessThanOrEqual(visible.x + visible.width);
  }
});

/** The axe violations of the page: rule id, impact and the first targets of each. */
async function axeViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return results.violations.map(
    (violation) =>
      `${violation.id} (${violation.impact ?? "?"}): ${violation.nodes
        .slice(0, 3)
        .map((node) => node.target.join(" "))
        .join(", ")}`,
  );
}

test("styling AC16: axe finds no WCAG 2.1 AA violation on any page", async ({ page }) => {
  const refused = async (target: Page) => {
    await target.goto("/yhteenveto?unit=month&from=2026-11&to=2026-10");
    await expect(target.getByRole("alert")).toBeVisible();
  };
  const found: Record<string, string[]> = {};
  for (const { name, open } of [...PAGES, { name: "Yhteenveto, virhe", open: refused }]) {
    await open(page);
    found[name] = await axeViolations(page);
  }

  expect(found).toEqual(Object.fromEntries(Object.keys(found).map((name) => [name, []])));
});
