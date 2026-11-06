import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, it, vi } from "vitest";
import indexHtml from "../index.html?raw";
import type { Health } from "./api/health";
import { App } from "./App";
import { fi } from "./i18n/fi";
import { answerBudget, answerComparison } from "./test/budget";
import { defaultItems, fakeCatalog } from "./test/catalog";
import { IDLE } from "./test/imports";
import { RECEIPT_A, RECEIPT_MANUAL, SUMMARY_A, SUMMARY_B } from "./test/receipts";
import { server } from "./test/server";
import { answerTotals } from "./test/totals";

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

// The product management spec's AC31 had one link; receipt-import AC26 adds "Tuonti",
// receipt-review PC7 "Kuitit", the totals spec PC4 "Yhteenveto" and the budget spec PC3 and
// PC6 "Budjetti" and "Vertailu".
it("AC31, AC26: the navigation opens the Tuotteet page", async () => {
  render(<App />);

  const navigation = screen.getByRole("navigation", { name: "Päävalikko" });
  const links = within(navigation).getAllByRole("link");
  expect(links.map((link) => link.textContent)).toEqual([
    "Tuotteet",
    "Tuonti",
    "Kuitit",
    "Yhteenveto",
    "Budjetti",
    "Vertailu",
  ]);
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

// Receipt review spec: the Kuitit page and one receipt.

function receiptAnswers() {
  server.use(
    http.get("/api/receipts", () => HttpResponse.json([SUMMARY_B, SUMMARY_A])),
    http.get("/api/receipts/3", () => HttpResponse.json(RECEIPT_A)),
  );
}

it("AC20: the Kuitit link opens the receipt list", async () => {
  receiptAnswers();
  const user = userEvent.setup();
  render(<App />);
  const navigation = screen.getByRole("navigation", { name: "Päävalikko" });

  await user.click(within(navigation).getByRole("link", { name: "Kuitit" }));

  const main = screen.getByRole("main");
  expect(within(main).getByRole("heading", { name: "Kuitit" })).toBeInTheDocument();
  expect(await within(main).findByRole("table", { name: "Kuittilista" })).toBeInTheDocument();
  expect(within(navigation).getByRole("link", { name: "Kuitit" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(window.location.pathname).toBe("/kuitit");
});

it("AC22: a receipt opens from the list and the back link returns", async () => {
  receiptAnswers();
  window.history.replaceState(null, "", "/kuitit");
  const user = userEvent.setup();
  render(<App />);

  await user.click(await screen.findByRole("link", { name: "5.10.2026" }));

  expect(window.location.pathname).toBe("/kuitit/3");
  expect(await screen.findByRole("heading", { name: "Kuitti" })).toBeInTheDocument();
  // The store is an input since line editing (line-editing PC12).
  expect(await screen.findByLabelText("Kauppa")).toHaveValue("Testikauppa");
  const navigation = screen.getByRole("navigation", { name: "Päävalikko" });
  expect(within(navigation).getByRole("link", { name: "Kuitit" })).toHaveAttribute(
    "aria-current",
    "page",
  );

  await user.click(screen.getByRole("link", { name: "Takaisin kuittilistaan" }));

  expect(window.location.pathname).toBe("/kuitit");
  expect(await screen.findByRole("table", { name: "Kuittilista" })).toBeInTheDocument();
});

it("AC22: a reload at /kuitit/<id> shows the receipt", async () => {
  receiptAnswers();
  window.history.replaceState(null, "", "/kuitit/3");
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Kuitti" })).toBeInTheDocument();
  // The store is an input since line editing (line-editing PC12).
  expect(await screen.findByLabelText("Kauppa")).toHaveValue("Testikauppa");
});

// Receipt management spec: delete a receipt, and type one in.

it("receipt-management AC25: a deleted receipt is gone from the list that opens", async () => {
  let deleted = false;
  server.use(
    http.get("/api/receipts", () =>
      HttpResponse.json(deleted ? [{ ...SUMMARY_B, reviewed: true }] : [SUMMARY_B, SUMMARY_A]),
    ),
    http.get("/api/receipts/3", () => HttpResponse.json(RECEIPT_A)),
    http.delete("/api/receipts/3", () => {
      deleted = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  window.history.replaceState(null, "", "/kuitit/3");
  const user = userEvent.setup();
  render(<App />);

  await user.click(await screen.findByRole("button", { name: "Poista kuitti" }));
  const review = screen.getByRole("button", { name: "Vahvista" });
  await user.click(within(review.parentElement!).getByRole("button", { name: "Poista" }));

  expect(await screen.findByRole("table", { name: "Kuittilista" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/kuitit");
  expect(deleted).toBe(true);
  expect(await screen.findByRole("link", { name: "6.10.2026" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "5.10.2026" })).toBeNull();
});

it("receipt-management AC29: a receipt typed in on the Kuitit page opens without an image", async () => {
  let body: unknown;
  let imageAsked = false;
  server.use(
    http.get("/api/receipts", () => HttpResponse.json([SUMMARY_A])),
    http.get("/api/failed-images", () => HttpResponse.json({ file_names: [] })),
    http.post("/api/receipts", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json(RECEIPT_MANUAL, { status: 201 });
    }),
    http.get("/api/receipts/7", () => HttpResponse.json(RECEIPT_MANUAL)),
    http.get("/api/receipts/7/image", () => {
      imageAsked = true;
      return new HttpResponse(null, { status: 404 });
    }),
  );
  window.history.replaceState(null, "", "/kuitit");
  const user = userEvent.setup();
  render(<App />);

  await user.click(screen.getByRole("button", { name: "Uusi kuitti" }));
  await user.type(screen.getByLabelText("Kauppa"), "Testikauppa");
  fireEvent.change(screen.getByLabelText("Päivä"), { target: { value: "2026-10-05" } });
  await user.type(screen.getByLabelText("Loppusumma"), "3,49");
  await user.click(screen.getByRole("button", { name: "Luo kuitti" }));

  expect(await screen.findByText("Ei kuvaa.")).toBeInTheDocument();
  expect(window.location.pathname).toBe("/kuitit/7");
  expect(body).toEqual({ store: "Testikauppa", purchase_date: "2026-10-05", total_cents: 349 });
  expect(screen.queryByRole("img")).toBeNull();
  expect(imageAsked).toBe(false);
});

// Budget spec: the Budjetti and Vertailu pages.

it("budget AC17: the Budjetti link opens the page", async () => {
  answerBudget();
  const user = userEvent.setup();
  render(<App />);
  const navigation = screen.getByRole("navigation", { name: "Päävalikko" });

  await user.click(within(navigation).getByRole("link", { name: "Budjetti" }));

  const main = screen.getByRole("main");
  expect(within(main).getByRole("heading", { name: "Budjetti" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/budjetti");
  expect(await within(main).findByRole("textbox", { name: "Auto" })).toBeInTheDocument();
});

it("budget AC19: the Vertailu link opens the page", async () => {
  answerComparison();
  const user = userEvent.setup();
  render(<App />);
  const navigation = screen.getByRole("navigation", { name: "Päävalikko" });

  await user.click(within(navigation).getByRole("link", { name: "Vertailu" }));

  const main = screen.getByRole("main");
  expect(within(main).getByRole("heading", { name: "Vertailu" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/vertailu");
  expect(await within(main).findByRole("table", { name: "Kuukausi" })).toBeInTheDocument();
});

it("budget P8: the Vertailu link on the Vertailu page keeps the chosen period", async () => {
  window.history.replaceState(null, "", "/vertailu?month=2026-10&period=mid");
  answerComparison();
  const user = userEvent.setup();
  render(<App />);
  const navigation = screen.getByRole("navigation", { name: "Päävalikko" });

  await user.click(within(navigation).getByRole("link", { name: "Vertailu" }));

  expect(window.location.search).toBe("?month=2026-10&period=mid");
  expect(await screen.findByRole("table", { name: "Kuukausi" })).toBeInTheDocument();
});

// Totals spec: the Yhteenveto page.

it("totals AC14: the Yhteenveto link opens the totals of the current month", async () => {
  vi.useFakeTimers({ toFake: ["Date"], now: new Date(2026, 10, 2, 12) });
  try {
    const queries = answerTotals();
    const user = userEvent.setup();
    render(<App />);
    const navigation = screen.getByRole("navigation", { name: "Päävalikko" });

    await user.click(within(navigation).getByRole("link", { name: "Yhteenveto" }));

    const main = screen.getByRole("main");
    expect(within(main).getByRole("heading", { name: "Yhteenveto" })).toBeInTheDocument();
    expect(await within(main).findByRole("table", { name: "Viikot" })).toBeInTheDocument();
    expect(within(navigation).getByRole("link", { name: "Yhteenveto" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(queries).toEqual(["unit=month&from=2026-11&to=2026-11"]);
    expect(window.location.pathname).toBe("/yhteenveto");
  } finally {
    vi.useRealTimers();
  }
});

it("totals PC5: the Yhteenveto link on the Yhteenveto page keeps the chosen period", async () => {
  window.history.replaceState(null, "", "/yhteenveto?unit=week&from=2026-W40&to=2026-W41");
  answerTotals();
  const user = userEvent.setup();
  render(<App />);
  const navigation = screen.getByRole("navigation", { name: "Päävalikko" });
  await screen.findByRole("table", { name: "Viikot" });
  const entries = window.history.length;

  await user.click(within(navigation).getByRole("link", { name: "Yhteenveto" }));

  expect(window.location.search).toBe("?unit=week&from=2026-W40&to=2026-W41");
  expect(window.history.length).toBe(entries);
  expect(screen.getByLabelText("Alkaen")).toHaveValue("2026-W40");
});
