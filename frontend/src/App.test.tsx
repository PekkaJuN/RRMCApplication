import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, it } from "vitest";
import indexHtml from "../index.html?raw";
import type { Health } from "./api/health";
import { App } from "./App";
import { fi } from "./i18n/fi";
import { defaultItems, fakeCatalog } from "./test/catalog";
import { IDLE } from "./test/imports";
import { server } from "./test/server";

const HEALTHY: Health = {
  status: "ok",
  model_name: "qwen2.5:7b",
  checks: { database: "ok", folders: "ok", ocr: "ok", model: "ok" },
};

beforeEach(() => {
  window.history.replaceState(null, "", "/");
  server.use(
    http.get("/api/health", () => HttpResponse.json(HEALTHY)),
    http.get("/api/import", () => HttpResponse.json(IDLE)),
  );
  fakeCatalog(server);
});

/** Every fixed text in `fi`; texts built from a value are added by the caller. */
function fixedTexts(value: unknown): string[] {
  if (typeof value === "string") {
    return [value];
  }
  if (typeof value === "object" && value !== null) {
    return Object.values(value).flatMap(fixedTexts);
  }
  return [];
}

/** The Finnish texts the shell and the Tuotteet page may show with the default list. */
function allowedTexts(): Set<string> {
  const names = defaultItems().map((item) => item.name);
  const counts = Array.from({ length: 30 }, (_, count) => [
    fi.categories.productCount(count),
    fi.categories.categoryCount(count),
  ]).flat();
  return new Set([
    ...fixedTexts(fi),
    ...names,
    ...names.map(fi.products.wholeGroup),
    ...names.map(fi.categories.move),
    ...counts,
  ]);
}

it("AC25: shows the heading, the navigation and the status line", async () => {
  render(<App />);

  expect(screen.getByRole("heading", { level: 1, name: "Kuittisovellus" })).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Päävalikko" })).toBeInTheDocument();
  expect(await screen.findByText("Kaikki palvelut toiminnassa")).toBeInTheDocument();
});

// The product management spec's AC31 had one link; receipt-import AC26 adds "Tuonti".
it("AC31, AC26: the navigation opens the Tuotteet page", async () => {
  render(<App />);

  const navigation = screen.getByRole("navigation", { name: "Päävalikko" });
  const links = within(navigation).getAllByRole("link");
  expect(links.map((link) => link.textContent)).toEqual(["Tuotteet", "Tuonti"]);
  expect(links[0]).toHaveAttribute("aria-current", "page");
  const main = screen.getByRole("main");
  expect(within(main).getByRole("heading", { name: "Tuotteet" })).toBeInTheDocument();
  expect(await within(main).findByText("Juomat", { selector: "[data-name]" })).toBeInTheDocument();
  expect(await screen.findByText("Kaikki palvelut toiminnassa")).toBeInTheDocument();
});

it("AC26: the Tuonti link opens the Tuonti page", async () => {
  const user = userEvent.setup();
  render(<App />);
  const navigation = screen.getByRole("navigation", { name: "Päävalikko" });

  await user.click(within(navigation).getByRole("link", { name: "Tuonti" }));

  const main = screen.getByRole("main");
  expect(within(main).getByRole("heading", { name: "Tuonti" })).toBeInTheDocument();
  expect(within(navigation).getByRole("link", { name: "Tuonti" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(within(navigation).getByRole("link", { name: "Tuotteet" })).not.toHaveAttribute(
    "aria-current",
  );
  expect(window.location.pathname).toBe("/tuonti");
  expect(await screen.findByText("Kaikki palvelut toiminnassa")).toBeInTheDocument();
});

it("AC25, AC30: shows no English text", async () => {
  const { container } = render(<App />);
  await screen.findByText("Kaikki palvelut toiminnassa");
  await screen.findByText("Ei tuotteita.");

  // Every visible text, accessible name and placeholder is one of the Finnish texts.
  const allowed = allowedTexts();
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const texts: string[] = [];
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.textContent?.trim();
    if (text) {
      texts.push(text);
    }
  }
  for (const attribute of ["aria-label", "placeholder", "label"]) {
    for (const element of container.querySelectorAll(`[${attribute}]`)) {
      texts.push(element.getAttribute(attribute) ?? "");
    }
  }
  expect(texts.filter((text) => !allowed.has(text))).toEqual([]);
});

it("AC25: the page is Finnish and the tab title is Kuittisovellus", () => {
  const page = new DOMParser().parseFromString(indexHtml, "text/html");

  expect(page.documentElement.lang).toBe("fi");
  expect(page.title).toBe("Kuittisovellus");
});
