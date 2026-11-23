import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, expect, it, vi } from "vitest";
import type { ReceiptSummary } from "../api/receipts";
import {
  ATTENTION_LIST,
  attentionReceipts,
  FAILED_IMAGES,
  FUTURE_UNREVIEWED,
  SUMMARY_A,
  SUMMARY_B,
} from "../test/receipts";
import { server } from "../test/server";
import { ReceiptsPage } from "./ReceiptsPage";

function listAnswers(receipts: ReceiptSummary[]) {
  server.use(http.get("/api/receipts", () => HttpResponse.json(receipts)));
}

async function rowTexts(): Promise<string[][]> {
  const table = await screen.findByRole("table", { name: "Kuittilista" });
  return within(table)
    .getAllByRole("row")
    .map((row) =>
      within(row)
        .queryAllByRole("cell")
        .map((cell) => cell.textContent ?? ""),
    )
    .filter((cells) => cells.length > 0);
}

it("AC20: the list shows every receipt with its summary", async () => {
  listAnswers([SUMMARY_B, SUMMARY_A]);
  render(<ReceiptsPage onOpen={() => {}} />);

  expect(screen.getByRole("heading", { name: "Kuitit" })).toBeInTheDocument();
  const table = await screen.findByRole("table", { name: "Kuittilista" });
  expect(
    within(table)
      .getAllByRole("columnheader")
      .map((header) => header.textContent),
  ).toEqual(["Päivä", "Kauppa", "Summa", "Varoitus", "Tila"]);
  expect(await rowTexts()).toEqual([
    ["6.10.2026", "Kauppa B", "5,00 €", "Summa ei täsmää", "Tarkistamaton"],
    ["5.10.2026", "Testikauppa", "3,49 €", "", "Vahvistettu"],
  ]);
});

it("AC21: an empty list", async () => {
  listAnswers([]);
  render(<ReceiptsPage onOpen={() => {}} />);

  expect(await screen.findByText("Ei kuitteja. Tuo kuitit Tuonti-sivulla.")).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("AC21: missing date, store and total show a dash", async () => {
  listAnswers([
    {
      id: 6,
      purchase_date: null,
      store: "",
      total_cents: null,
      warning: true,
      reviewed: false,
    },
  ]);
  render(<ReceiptsPage onOpen={() => {}} />);

  expect(await rowTexts()).toEqual([["–", "–", "–", "Summa ei täsmää", "Tarkistamaton"]]);
});

it("AC22: the date link opens the receipt", async () => {
  listAnswers([SUMMARY_B, SUMMARY_A]);
  const onOpen = vi.fn();
  const user = userEvent.setup();
  render(<ReceiptsPage onOpen={onOpen} />);

  const link = await screen.findByRole("link", { name: "5.10.2026" });
  expect(link).toHaveAttribute("href", "/kuitit/3");
  await user.click(link);

  expect(onOpen).toHaveBeenCalledWith(3);
});

it("AC29: a list that cannot be loaded shows the error", async () => {
  server.use(http.get("/api/receipts", () => HttpResponse.error()));
  render(<ReceiptsPage onOpen={() => {}} />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Taustapalveluun ei saada yhteyttä.");
});

it("receipt-management AC34: the new receipt form opens empty again after cancel", async () => {
  server.use(
    http.get("/api/receipts", () => HttpResponse.json([SUMMARY_A])),
    http.get("/api/failed-images", () => HttpResponse.json({ file_names: FAILED_IMAGES })),
  );
  const user = userEvent.setup();
  render(<ReceiptsPage onOpen={() => {}} />);

  await user.click(screen.getByRole("button", { name: "Uusi kuitti" }));
  // By role: the store search radio is also labelled Kauppa (store search P6).
  await user.type(screen.getByRole("textbox", { name: "Kauppa" }), "Testikauppa");
  const select = screen.getByLabelText("Kuva");
  await waitFor(() => expect(within(select).getAllByRole("option")).toHaveLength(4));
  await user.selectOptions(select, "IMG_2.jpg");
  await user.click(screen.getByRole("button", { name: "Peruuta" }));

  expect(screen.queryByRole("form", { name: "Uusi kuitti" })).toBeNull();
  await user.click(screen.getByRole("button", { name: "Uusi kuitti" }));
  expect(screen.getByRole("textbox", { name: "Kauppa" })).toHaveValue("");
  expect(screen.getByLabelText("Kuva")).toHaveDisplayValue("Ei kuvaa");
});

// Note on old and undated unreviewed receipts (specs/features/unreviewed-receipts-note.md).

afterEach(() => {
  vi.useRealTimers();
});

/** Fixes today; only Date is faked, so fetch and MSW keep their real timers. */
function today(iso = "2026-06-15T09:00:00Z") {
  vi.useFakeTimers({ toFake: ["Date"], now: new Date(iso) });
}

async function noteText(): Promise<string> {
  return (await screen.findByRole("status")).querySelector("p")?.textContent ?? "";
}

const filterButton = () => screen.getByRole("button", { name: "Näytä vain nämä kuitit" });

async function storesShown(): Promise<string[]> {
  return (await rowTexts()).map((cells) => cells[1] ?? "");
}

const ALL_STORES = ATTENTION_LIST.map((receipt) => receipt.store);

it("unreviewed-note AC1: the note names both kinds and has the filter button", async () => {
  today();
  listAnswers(ATTENTION_LIST);
  render(<ReceiptsPage onOpen={() => {}} />);

  expect(await noteText()).toBe(
    "Tarkistamattomia kuitteja ilman päivämäärää: 1. " +
      "Tarkistamattomia kuitteja edellisiltä vuosilta: 3 (2024, 2025).",
  );
  const note = screen.getByRole("status");
  expect(within(note).getByRole("button", { name: "Näytä vain nämä kuitit" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  expect(
    note.compareDocumentPosition(screen.getByRole("table", { name: "Kuittilista" })) &
      Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
  expect(await storesShown()).toEqual(ALL_STORES);
});

it("unreviewed-note AC2: only undated receipts", async () => {
  today();
  listAnswers(attentionReceipts(1, 2, 3));
  render(<ReceiptsPage onOpen={() => {}} />);

  expect(await noteText()).toBe("Tarkistamattomia kuitteja ilman päivämäärää: 1.");
});

it("unreviewed-note AC3: only receipts of earlier years", async () => {
  today();
  listAnswers(attentionReceipts(3, 4, 5, 6));
  render(<ReceiptsPage onOpen={() => {}} />);

  expect(await noteText()).toBe("Tarkistamattomia kuitteja edellisiltä vuosilta: 3 (2024, 2025).");
});

it("unreviewed-note AC4: no note without receipts that need attention", async () => {
  today();
  listAnswers([...attentionReceipts(2, 3, 7), FUTURE_UNREVIEWED]);
  render(<ReceiptsPage onOpen={() => {}} />);

  await screen.findByRole("table", { name: "Kuittilista" });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Näytä vain nämä kuitit" })).not.toBeInTheDocument();
});

it("unreviewed-note AC7: the year turns at Finnish midnight", async () => {
  today("2025-12-31T22:30:00Z");
  listAnswers(attentionReceipts(3, 4));
  render(<ReceiptsPage onOpen={() => {}} />);

  expect(await noteText()).toBe("Tarkistamattomia kuitteja edellisiltä vuosilta: 1 (2025).");
});

it("unreviewed-note AC8: a failed list shows the alert and no note", async () => {
  today();
  server.use(
    http.get("/api/receipts", () =>
      HttpResponse.json(
        { error: "internal_error", message: "Jokin meni pieleen." },
        { status: 500 },
      ),
    ),
  );
  render(<ReceiptsPage onOpen={() => {}} />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Jokin meni pieleen.");
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("unreviewed-note AC5, AC6: the filter shows only these receipts, then all", async () => {
  today();
  listAnswers(ATTENTION_LIST);
  const user = userEvent.setup();
  render(<ReceiptsPage onOpen={() => {}} />);
  await screen.findByRole("status");

  await user.click(filterButton());

  expect(await storesShown()).toEqual(["Kauppa 1", "Kauppa 4", "Kauppa 5", "Kauppa 6"]);
  expect(filterButton()).toHaveAttribute("aria-pressed", "true");
  expect(await noteText()).toBe(
    "Tarkistamattomia kuitteja ilman päivämäärää: 1. " +
      "Tarkistamattomia kuitteja edellisiltä vuosilta: 3 (2024, 2025).",
  );

  await user.click(filterButton());

  expect(await storesShown()).toEqual(ALL_STORES);
  expect(filterButton()).toHaveAttribute("aria-pressed", "false");
});

// Receipt search (specs/features/receipt-search.md). R1–R4 are reviewed, R5 is unreviewed
// and undated, as in the spec's test data; the backend's answers are fixed per query.

function searchReceipt(name: string, purchase_date: string | null, reviewed = true) {
  return {
    id: Number(name.slice(1)),
    purchase_date,
    store: `Kauppa ${name}`,
    total_cents: 100,
    warning: false,
    reviewed,
  } satisfies ReceiptSummary;
}

const R1 = searchReceipt("R1", "2026-10-05");
const R2 = searchReceipt("R2", "2026-10-04");
const R3 = searchReceipt("R3", "2026-10-03");
const R4 = searchReceipt("R4", "2026-10-02");
const R5 = searchReceipt("R5", null, false);
const SEARCH_ALL = [R5, R1, R2, R3, R4];

const SEARCH_ANSWERS: Record<string, ReceiptSummary[]> = {
  "": SEARCH_ALL,
  "?name=maito": [R1, R4],
  "?uncategorized=true": [R2, R4],
  "?name=maito&uncategorized=true": [R4],
  "?name=banaani": [],
};

/** Answers GET /api/receipts by its query string and records each query string. */
function searchServer(): string[] {
  const searches: string[] = [];
  server.use(
    http.get("/api/receipts", ({ request }) => {
      const search = new URL(request.url).search;
      searches.push(search);
      return HttpResponse.json(SEARCH_ANSWERS[search] ?? []);
    }),
  );
  return searches;
}

// Store search AC9 renamed the field from "Hae tuotteella" (store search P6).
const searchField = () => screen.getByRole("searchbox", { name: "Hakusana" });
const searchButton = () => screen.getByRole("button", { name: "Hae" });
const uncategorizedBox = () =>
  screen.getByRole("checkbox", { name: "Vain kuitit, joilla on rivejä ilman kategoriaa" });
const NO_MATCHES = "Hakuehdoilla ei löytynyt kuitteja.";

async function renderSearchPage() {
  today("2026-11-22T09:00:00Z");
  const searches = searchServer();
  const user = userEvent.setup();
  render(<ReceiptsPage onOpen={() => {}} />);
  await screen.findByRole("table", { name: "Kuittilista" });
  return { searches, user };
}

it("receipt search AC9: Enter searches by product name, an empty search shows all", async () => {
  const { searches, user } = await renderSearchPage();

  await user.type(searchField(), "maito{Enter}");

  await waitFor(async () => expect(await storesShown()).toEqual(["Kauppa R1", "Kauppa R4"]));
  expect(searches).toEqual(["", "?name=maito"]);

  await user.clear(searchField());
  await user.click(searchButton());

  await waitFor(async () =>
    expect(await storesShown()).toEqual(SEARCH_ALL.map((receipt) => receipt.store)),
  );
  // No condition shows the list loaded when the page opened, without a request.
  expect(searches).toEqual(["", "?name=maito"]);
});

it("receipt search AC9: the Hae button searches", async () => {
  const { user } = await renderSearchPage();

  await user.type(searchField(), "maito");
  await user.click(searchButton());

  await waitFor(async () => expect(await storesShown()).toEqual(["Kauppa R1", "Kauppa R4"]));
});

it("receipt search AC10: the checkbox filters at once, and unchecking shows all", async () => {
  const { searches, user } = await renderSearchPage();

  await user.click(uncategorizedBox());

  await waitFor(async () => expect(await storesShown()).toEqual(["Kauppa R2", "Kauppa R4"]));
  expect(searches).toEqual(["", "?uncategorized=true"]);

  await user.click(uncategorizedBox());

  await waitFor(async () =>
    expect(await storesShown()).toEqual(SEARCH_ALL.map((receipt) => receipt.store)),
  );
  expect(uncategorizedBox()).not.toBeChecked();
});

it("receipt search AC10: the checkbox uses the searched text, not unsent typing", async () => {
  const { searches, user } = await renderSearchPage();

  await user.type(searchField(), "maito{Enter}");
  await waitFor(async () => expect(await storesShown()).toEqual(["Kauppa R1", "Kauppa R4"]));
  await user.type(searchField(), "x");
  await user.click(uncategorizedBox());

  await waitFor(async () => expect(await storesShown()).toEqual(["Kauppa R4"]));
  expect(searches).toEqual(["", "?name=maito", "?name=maito&uncategorized=true"]);
});

it("receipt search AC12: no match shows the text and keeps the search", async () => {
  const { user } = await renderSearchPage();

  await user.type(searchField(), "banaani{Enter}");

  expect(await screen.findByText(NO_MATCHES)).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(searchField()).toHaveValue("banaani");
});

it("receipt search AC14: the search text is at most 100 characters", async () => {
  await renderSearchPage();

  expect(searchField()).toHaveAttribute("maxLength", "100");
});

it("receipt search P6: a slow earlier answer does not replace a later one", async () => {
  today("2026-11-22T09:00:00Z");
  let releaseSlow: () => void = () => {};
  const slow = new Promise<void>((resolve) => {
    releaseSlow = resolve;
  });
  server.use(
    http.get("/api/receipts", async ({ request }) => {
      const search = new URL(request.url).search;
      if (search === "?name=maito") {
        await slow;
      }
      return HttpResponse.json(SEARCH_ANSWERS[search] ?? []);
    }),
  );
  const user = userEvent.setup();
  render(<ReceiptsPage onOpen={() => {}} />);
  await screen.findByRole("table", { name: "Kuittilista" });

  await user.type(searchField(), "maito{Enter}");
  await user.clear(searchField());
  await user.type(searchField(), "banaani{Enter}");
  expect(await screen.findByText(NO_MATCHES)).toBeInTheDocument();
  releaseSlow();

  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(screen.getByText(NO_MATCHES)).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("receipt search AC11: the note counts every receipt, the toggle filters the result", async () => {
  const { user } = await renderSearchPage();
  const note = "Tarkistamattomia kuitteja ilman päivämäärää: 1.";
  expect(await noteText()).toBe(note);

  await user.type(searchField(), "maito{Enter}");
  await waitFor(async () => expect(await storesShown()).toEqual(["Kauppa R1", "Kauppa R4"]));
  expect(await noteText()).toBe(note);

  await user.click(filterButton());

  expect(await screen.findByText(NO_MATCHES)).toBeInTheDocument();
  expect(await noteText()).toBe(note);
});

it.each([
  [
    "an error answer",
    () =>
      HttpResponse.json(
        { error: "internal_error", message: "Jokin meni pieleen." },
        { status: 500 },
      ),
    "Jokin meni pieleen.",
  ],
  ["no connection", () => HttpResponse.error(), "Taustapalveluun ei saada yhteyttä."],
])("receipt search AC13: %s shows the alert and keeps the values", async (_, fail, message) => {
  const { user } = await renderSearchPage();
  server.use(
    http.get("/api/receipts", ({ request }) =>
      new URL(request.url).search === "?name=maito&uncategorized=true"
        ? fail()
        : HttpResponse.json(SEARCH_ANSWERS[new URL(request.url).search] ?? []),
    ),
  );

  await user.type(searchField(), "maito");
  await user.click(uncategorizedBox());
  await waitFor(async () => expect(await storesShown()).toEqual(["Kauppa R2", "Kauppa R4"]));
  await user.click(searchButton());

  expect(await screen.findByRole("alert")).toHaveTextContent(message);
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(searchField()).toHaveValue("maito");
  expect(uncategorizedBox()).toBeChecked();

  await user.click(uncategorizedBox());

  await waitFor(async () => expect(await storesShown()).toEqual(["Kauppa R1", "Kauppa R4"]));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

// Store search (specs/features/store-search.md).

const targetGroup = () => screen.getByRole("group", { name: "Hakukohde" });
const productTarget = () => screen.getByRole("radio", { name: "Tuote" });
const storeTarget = () => screen.getByRole("radio", { name: "Kauppa" });

it("store search AC9: the form has the field, the target, the button and the checkbox", async () => {
  const { searches, user } = await renderSearchPage();

  expect(searchField()).toHaveAttribute("maxLength", "100");
  expect(targetGroup()).toContainElement(productTarget());
  expect(targetGroup()).toContainElement(storeTarget());
  expect(productTarget()).toBeChecked();
  expect(storeTarget()).not.toBeChecked();
  expect(searchButton()).toBeInTheDocument();
  expect(uncategorizedBox()).not.toBeChecked();

  await user.type(searchField(), "maito{Enter}");

  await waitFor(async () => expect(await storesShown()).toEqual(["Kauppa R1", "Kauppa R4"]));
  expect(searches).toEqual(["", "?name=maito"]);
});

// S1–S6 of the store search spec; the backend's answers are fixed per query.

function storeReceipt(id: number, store: string | null, purchase_date: string | null) {
  return {
    id,
    purchase_date,
    store,
    total_cents: 100,
    warning: false,
    reviewed: true,
  } satisfies ReceiptSummary;
}

const S1 = storeReceipt(11, "K-Market Keskusta", "2026-10-05");
const S2 = storeReceipt(12, "Prisma Itäkeskus", "2026-10-04");
const S3 = storeReceipt(13, "K-Citymarket", "2026-10-03");
const S4 = storeReceipt(14, "", "2026-10-02");
const S5 = storeReceipt(15, null, null);
const S6 = storeReceipt(16, "ÄRRÄ Asema", "2026-10-01");
const STORE_ALL = [S5, S1, S2, S3, S4, S6];

const STORE_ANSWERS: Record<string, ReceiptSummary[]> = {
  "": STORE_ALL,
  "?store=market": [S1, S3],
  "?name=market": [],
  "?uncategorized=true": [S2, S3],
  "?store=k&uncategorized=true": [S2, S3],
  "?store=lidl": [],
};

async function renderStorePage() {
  today("2026-11-23T09:00:00Z");
  const searches: string[] = [];
  server.use(
    http.get("/api/receipts", ({ request }) => {
      const search = new URL(request.url).search;
      searches.push(search);
      return HttpResponse.json(STORE_ANSWERS[search] ?? []);
    }),
  );
  const user = userEvent.setup();
  render(<ReceiptsPage onOpen={() => {}} />);
  await screen.findByRole("table", { name: "Kuittilista" });
  return { searches, user };
}

it("store search AC10: Kauppa and Enter search by store", async () => {
  const { searches, user } = await renderStorePage();

  await user.click(storeTarget());
  await user.type(searchField(), "market{Enter}");

  await waitFor(async () =>
    expect(await storesShown()).toEqual(["K-Market Keskusta", "K-Citymarket"]),
  );
  expect(searches).toEqual(["", "?store=market"]);
});

it("store search AC10: Kauppa and the Hae button search by store", async () => {
  const { searches, user } = await renderStorePage();

  await user.click(storeTarget());
  await user.type(searchField(), "market");
  await user.click(searchButton());

  await waitFor(async () =>
    expect(await storesShown()).toEqual(["K-Market Keskusta", "K-Citymarket"]),
  );
  expect(searches).toEqual(["", "?store=market"]);
});

it("store search AC11: changing the target searches again with the searched text", async () => {
  const { searches, user } = await renderStorePage();
  await user.click(storeTarget());
  await user.type(searchField(), "market{Enter}");
  await waitFor(async () =>
    expect(await storesShown()).toEqual(["K-Market Keskusta", "K-Citymarket"]),
  );

  await user.type(searchField(), "x");
  await user.click(productTarget());

  expect(await screen.findByText(NO_MATCHES)).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(searches).toEqual(["", "?store=market", "?name=market"]);
});

it("store search AC11: without a searched text, changing the target sends nothing", async () => {
  const { searches, user } = await renderStorePage();

  await user.click(storeTarget());

  expect(storeTarget()).toBeChecked();
  expect(await storesShown()).toEqual([
    "–",
    "K-Market Keskusta",
    "Prisma Itäkeskus",
    "K-Citymarket",
    "–",
    "ÄRRÄ Asema",
  ]);
  expect(searches).toEqual([""]);

  // With the checkbox on, the target change still sends nothing new.
  await user.click(uncategorizedBox());
  await waitFor(async () =>
    expect(await storesShown()).toEqual(["Prisma Itäkeskus", "K-Citymarket"]),
  );
  await user.click(productTarget());

  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(searches).toEqual(["", "?uncategorized=true"]);
});

it("store search AC12: store search with the checkbox", async () => {
  const { searches, user } = await renderStorePage();

  await user.click(storeTarget());
  await user.type(searchField(), "k{Enter}");
  await user.click(uncategorizedBox());

  await waitFor(async () =>
    expect(await storesShown()).toEqual(["Prisma Itäkeskus", "K-Citymarket"]),
  );
  expect(searches).toContain("?store=k&uncategorized=true");
});

it("store search AC13: no match, then an error keeps the text and Kauppa", async () => {
  const { user } = await renderStorePage();

  await user.click(storeTarget());
  await user.type(searchField(), "lidl{Enter}");

  expect(await screen.findByText(NO_MATCHES)).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();

  server.use(
    http.get("/api/receipts", () =>
      HttpResponse.json(
        { error: "internal_error", message: "Jokin meni pieleen." },
        { status: 500 },
      ),
    ),
  );
  await user.clear(searchField());
  await user.type(searchField(), "virhe{Enter}");

  expect(await screen.findByRole("alert")).toHaveTextContent("Jokin meni pieleen.");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(searchField()).toHaveValue("virhe");
  expect(storeTarget()).toBeChecked();
});
