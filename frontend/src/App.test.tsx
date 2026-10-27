import { render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, it } from "vitest";
import indexHtml from "../index.html?raw";
import type { Health } from "./api/health";
import { App } from "./App";
import { fi } from "./i18n/fi";
import { defaultItems, fakeCatalog } from "./test/catalog";
import { server } from "./test/server";

const HEALTHY: Health = {
  status: "ok",
  model_name: "qwen2.5:7b",
  checks: { database: "ok", folders: "ok", ocr: "ok", model: "ok" },
};

beforeEach(() => {
  server.use(http.get("/api/health", () => HttpResponse.json(HEALTHY)));
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

it("AC31: the navigation opens the Tuotteet page", async () => {
  render(<App />);

  const navigation = screen.getByRole("navigation", { name: "Päävalikko" });
  const links = within(navigation).getAllByRole("link");
  expect(links.map((link) => link.textContent)).toEqual(["Tuotteet"]);
  expect(links[0]).toHaveAttribute("aria-current", "page");
  const main = screen.getByRole("main");
  expect(within(main).getByRole("heading", { name: "Tuotteet" })).toBeInTheDocument();
  expect(await within(main).findByText("Juomat", { selector: "[data-name]" })).toBeInTheDocument();
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
