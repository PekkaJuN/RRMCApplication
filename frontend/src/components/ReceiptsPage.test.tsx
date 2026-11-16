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
  await user.type(screen.getByLabelText("Kauppa"), "Testikauppa");
  const select = screen.getByLabelText("Kuva");
  await waitFor(() => expect(within(select).getAllByRole("option")).toHaveLength(4));
  await user.selectOptions(select, "IMG_2.jpg");
  await user.click(screen.getByRole("button", { name: "Peruuta" }));

  expect(screen.queryByRole("form", { name: "Uusi kuitti" })).toBeNull();
  await user.click(screen.getByRole("button", { name: "Uusi kuitti" }));
  expect(screen.getByLabelText("Kauppa")).toHaveValue("");
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
