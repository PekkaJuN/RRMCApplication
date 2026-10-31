import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, it, vi } from "vitest";
import type { ReceiptSummary } from "../api/receipts";
import { SUMMARY_A, SUMMARY_B } from "../test/receipts";
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
