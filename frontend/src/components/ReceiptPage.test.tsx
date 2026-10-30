import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, it, vi } from "vitest";
import type { Receipt } from "../api/receipts";
import {
  DAIRY,
  ITEMS,
  RECEIPT_A,
  RECEIPT_A_LIMU_DAIRY,
  RECEIPT_A_MORE,
  RECEIPT_AC8,
  RECEIPT_OLD,
} from "../test/receipts";
import { server } from "../test/server";
import { ReceiptPage } from "./ReceiptPage";

function answers(receipt: Receipt) {
  server.use(
    http.get(`/api/receipts/${receipt.id}`, () => HttpResponse.json(receipt)),
    http.get("/api/categories", () => HttpResponse.json(ITEMS)),
  );
}

function selectedText(select: HTMLElement): string {
  const element = select as HTMLSelectElement;
  return element.selectedOptions[0]?.textContent ?? "";
}

async function lineRows(): Promise<HTMLElement[]> {
  const table = await screen.findByRole("table", { name: "Kuittirivit" });
  return within(table).getAllByRole("row").slice(1);
}

it("AC22: the receipt with its image and lines", async () => {
  answers(RECEIPT_A);
  const onBack = vi.fn();
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={onBack} />);

  expect(await screen.findByRole("heading", { name: "Kuitti" })).toBeInTheDocument();
  expect(await screen.findByText("Testikauppa")).toBeInTheDocument();
  expect(screen.getByText("5.10.2026")).toBeInTheDocument();
  expect(screen.getByText("3,49 €")).toBeInTheDocument();
  expect(screen.getByText("Tarkistamaton")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Vahvista" })).toBeInTheDocument();

  const image = screen.getByRole("img", { name: "Kuitin kuva" });
  expect(image).toHaveAttribute("src", "/api/receipts/3/image");
  const imageLink = image.closest("a");
  expect(imageLink).toHaveAttribute("href", "/api/receipts/3/image");
  expect(imageLink).toHaveAttribute("target", "_blank");

  const rows = await lineRows();
  expect(rows.map((row) => within(row).getAllByRole("cell")[0]?.textContent)).toEqual([
    "Maito",
    "Limu",
  ]);
  expect(rows.map((row) => within(row).getAllByRole("cell")[1]?.textContent)).toEqual([
    "1,25 €",
    "2,24 €",
  ]);

  const back = screen.getByRole("link", { name: "Takaisin kuittilistaan" });
  expect(back).toHaveAttribute("href", "/kuitit");
  await user.click(back);
  expect(onBack).toHaveBeenCalled();
});

it("AC23: line categories, the model mark and the deposit refund", async () => {
  answers(RECEIPT_A_MORE);
  render(<ReceiptPage id={3} onBack={() => {}} />);

  const milk = await screen.findByRole("combobox", { name: "Kategoria: Maito" });
  const soda = screen.getByRole("combobox", { name: "Kategoria: Limu" });
  const odd = screen.getByRole("combobox", { name: "Kategoria: Outo" });
  expect(selectedText(milk)).toBe("Maitotuotteet");
  expect(selectedText(soda)).toBe("Juomat");
  expect(selectedText(odd)).toBe("Valitse kategoria");
  expect(screen.queryByRole("combobox", { name: "Kategoria: Panttipalautus" })).toBeNull();

  const rows = await lineRows();
  const [milkRow, sodaRow, , refundRow] = rows;
  expect(within(milkRow!).queryByText("ehdotus")).toBeNull();
  expect(within(sodaRow!).getByText("ehdotus")).toBeInTheDocument();
  expect(within(refundRow!).getByText("Pantinpalautus")).toBeInTheDocument();
  expect(within(refundRow!).getByText("-0,40 €")).toBeInTheDocument();

  // Groups are headings, not options (FR-17).
  const groups = Array.from(milk.querySelectorAll("optgroup")).map((group) => group.label);
  expect(groups).toEqual(["Auto", "Ruoka"]);
  expect(within(milk).queryByRole("option", { name: "Ruoka" })).toBeNull();
});

it("AC25: line sum, subtotals and the warning", async () => {
  answers(RECEIPT_AC8);
  render(<ReceiptPage id={5} onBack={() => {}} />);

  expect(await screen.findByText("Rivien summa 4,58 €")).toBeInTheDocument();
  const subtotals = screen.getByRole("list", { name: "Kategoriat" });
  expect(
    within(subtotals)
      .getAllByRole("listitem")
      .map((item) => item.textContent),
  ).toEqual(["Ruoka > Maitotuotteet 2,24 €", "Juomat 2,24 €", "Ei kategoriaa 0,50 €"]);
  expect(screen.getByRole("status")).toHaveTextContent(
    "Rivien summa 4,58 € poikkeaa loppusummasta 5,00 €. Erotus 0,42 €.",
  );
});

it("AC25: a receipt that adds up shows no warning", async () => {
  answers(RECEIPT_A);
  render(<ReceiptPage id={3} onBack={() => {}} />);

  await screen.findByText("Rivien summa 3,49 €");
  expect(screen.queryByRole("status")).toBeNull();
});

it("AC26: no total and no lines", async () => {
  answers(RECEIPT_OLD);
  render(<ReceiptPage id={6} onBack={() => {}} />);

  expect(await screen.findByText("Kuitilta ei luettu rivejä.")).toBeInTheDocument();
  expect(screen.getAllByText("–")).toHaveLength(3);
  expect(screen.getByRole("status")).toHaveTextContent("Loppusumma puuttuu.");
  expect(screen.queryByRole("table", { name: "Kuittirivit" })).toBeNull();
});

it("AC29: a receipt that does not exist", async () => {
  server.use(
    http.get("/api/receipts/999", () =>
      HttpResponse.json(
        { error: "not_found", message: "Pyydettyä kohdetta ei löydy." },
        { status: 404 },
      ),
    ),
    http.get("/api/categories", () => HttpResponse.json(ITEMS)),
  );
  render(<ReceiptPage id={999} onBack={() => {}} />);

  expect(await screen.findByText("Kuittia ei löydy.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Takaisin kuittilistaan" })).toBeInTheDocument();
});

it("AC29: a receipt that cannot be loaded shows the error", async () => {
  server.use(
    http.get("/api/receipts/3", () => HttpResponse.error()),
    http.get("/api/categories", () => HttpResponse.json(ITEMS)),
  );
  render(<ReceiptPage id={3} onBack={() => {}} />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Taustapalveluun ei saada yhteyttä.");
  expect(screen.getByRole("link", { name: "Takaisin kuittilistaan" })).toBeInTheDocument();
});

it("AC29: an image missing from the done folder is replaced by a text", async () => {
  answers(RECEIPT_A);
  render(<ReceiptPage id={3} onBack={() => {}} />);

  fireEvent.error(await screen.findByRole("img", { name: "Kuitin kuva" }));

  expect(await screen.findByText("Kuvaa ei löydy valmiiden kansiosta.")).toBeInTheDocument();
  expect(screen.queryByRole("img", { name: "Kuitin kuva" })).toBeNull();
  expect(await lineRows()).toHaveLength(2);
});

it("AC29: categories that cannot be loaded disable the dropdowns", async () => {
  server.use(
    http.get("/api/receipts/3", () => HttpResponse.json(RECEIPT_A)),
    http.get("/api/categories", () => HttpResponse.error()),
  );
  render(<ReceiptPage id={3} onBack={() => {}} />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Taustapalveluun ei saada yhteyttä.");
  expect(await screen.findByRole("combobox", { name: "Kategoria: Maito" })).toBeDisabled();
});

// Actions (T17)

it("AC24: choosing a category saves it and shows the answer", async () => {
  answers(RECEIPT_A);
  let body: unknown;
  let answer: () => void = () => {};
  server.use(
    http.patch("/api/receipts/3/lines/102", async ({ request }) => {
      body = await request.json();
      // Hold the answer, so the page can be checked while it waits.
      await new Promise<void>((resolve) => {
        answer = resolve;
      });
      return HttpResponse.json(RECEIPT_A_LIMU_DAIRY);
    }),
  );
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);
  const soda = await screen.findByRole("combobox", { name: "Kategoria: Limu" });
  await waitFor(() => expect(soda).toBeEnabled());

  await user.selectOptions(soda, "Maitotuotteet");

  await waitFor(() => expect(body).toEqual({ category_id: DAIRY.id }));
  expect(screen.getByRole("combobox", { name: "Kategoria: Maito" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Vahvista" })).toBeDisabled();
  answer();

  await waitFor(() =>
    expect(selectedText(screen.getByRole("combobox", { name: "Kategoria: Limu" }))).toBe(
      "Maitotuotteet",
    ),
  );
  expect(screen.queryByText("ehdotus")).toBeNull();
  expect(
    within(screen.getByRole("list", { name: "Kategoriat" }))
      .getAllByRole("listitem")
      .map((item) => item.textContent),
  ).toEqual(["Ruoka > Maitotuotteet 3,49 €"]);
  expect(screen.getByRole("combobox", { name: "Kategoria: Maito" })).toBeEnabled();
});

it("AC27: confirming and cancelling the confirmation", async () => {
  answers(RECEIPT_A);
  const bodies: unknown[] = [];
  server.use(
    http.patch("/api/receipts/3", async ({ request }) => {
      const body = (await request.json()) as { reviewed: boolean };
      bodies.push(body);
      return HttpResponse.json({ ...RECEIPT_A, reviewed: body.reviewed });
    }),
  );
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);

  await user.click(await screen.findByRole("button", { name: "Vahvista" }));

  expect(await screen.findByText("Vahvistettu")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Peru vahvistus" }));

  expect(await screen.findByText("Tarkistamaton")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Vahvista" })).toBeInTheDocument();
  expect(bodies).toEqual([{ reviewed: true }, { reviewed: false }]);
});

it("AC28: a refused category choice shows the message by its line", async () => {
  answers(RECEIPT_A);
  server.use(
    http.patch("/api/receipts/3/lines/102", () =>
      HttpResponse.json(
        {
          error: "deposit_refund_line",
          message: "Pantinpalautusriville ei voi valita kategoriaa.",
        },
        { status: 422 },
      ),
    ),
  );
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);
  const soda = await screen.findByRole("combobox", { name: "Kategoria: Limu" });
  await waitFor(() => expect(soda).toBeEnabled());

  await user.selectOptions(soda, "Maitotuotteet");

  const [, sodaRow] = await lineRows();
  expect(await within(sodaRow!).findByRole("alert")).toHaveTextContent(
    "Pantinpalautusriville ei voi valita kategoriaa.",
  );
  expect(selectedText(screen.getByRole("combobox", { name: "Kategoria: Limu" }))).toBe("Juomat");
});

it("AC28: a failed confirmation shows the message by the button", async () => {
  answers(RECEIPT_A);
  server.use(http.patch("/api/receipts/3", () => HttpResponse.error()));
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);

  const button = await screen.findByRole("button", { name: "Vahvista" });
  await user.click(button);

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Taustapalveluun ei saada yhteyttä.");
  expect(button.parentElement).toContainElement(alert);
  expect(screen.getByText("Tarkistamaton")).toBeInTheDocument();
});

// Audit follow-ups: the labels of the header and the table, and a line error that clears.

it("AC22: the field labels and line columns", async () => {
  answers(RECEIPT_A);
  render(<ReceiptPage id={3} onBack={() => {}} />);

  const table = await screen.findByRole("table", { name: "Kuittirivit" });
  expect(
    within(table)
      .getAllByRole("columnheader")
      .map((header) => header.textContent),
  ).toEqual(["Tuote", "Summa", "Kategoria"]);
  for (const label of ["Kauppa", "Päivä", "Loppusumma"]) {
    expect(screen.getByText(label, { selector: "dt" })).toBeInTheDocument();
  }
});

it("AC28: a line's error clears on its next successful choice", async () => {
  answers(RECEIPT_A);
  let calls = 0;
  server.use(
    http.patch("/api/receipts/3/lines/102", () => {
      calls += 1;
      return calls === 1
        ? HttpResponse.json(
            { error: "unknown_category", message: "Kategoriaa ei löydy." },
            { status: 422 },
          )
        : HttpResponse.json(RECEIPT_A_LIMU_DAIRY);
    }),
  );
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);
  const soda = await screen.findByRole("combobox", { name: "Kategoria: Limu" });
  await waitFor(() => expect(soda).toBeEnabled());

  await user.selectOptions(soda, "Maitotuotteet");
  expect(await screen.findByRole("alert")).toHaveTextContent("Kategoriaa ei löydy.");
  await waitFor(() => expect(soda).toBeEnabled());
  await user.selectOptions(soda, "Maitotuotteet");

  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect(selectedText(screen.getByRole("combobox", { name: "Kategoria: Limu" }))).toBe(
    "Maitotuotteet",
  );
});
