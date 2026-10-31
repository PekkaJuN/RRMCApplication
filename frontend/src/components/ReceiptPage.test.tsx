import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, it, vi } from "vitest";
import type { Receipt } from "../api/receipts";
import {
  DAIRY,
  DRINKS,
  ITEMS,
  line,
  RECEIPT_A,
  RECEIPT_A_LIMU_DAIRY,
  RECEIPT_A_MORE,
  RECEIPT_AC8,
  RECEIPT_OLD,
  recordWrites,
  type RecordedWrite,
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

function inputValue(input: HTMLElement): string {
  return (input as HTMLInputElement).value;
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
  // Line editing turned the fields into inputs (line-editing PC12).
  expect(await screen.findByLabelText("Kauppa")).toHaveValue("Testikauppa");
  expect(screen.getByLabelText("Päivä")).toHaveValue("2026-10-05");
  expect(screen.getByLabelText("Loppusumma")).toHaveValue("3,49");
  expect(screen.getByText("Tarkistamaton")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Vahvista" })).toBeInTheDocument();

  const image = screen.getByRole("img", { name: "Kuitin kuva" });
  expect(image).toHaveAttribute("src", "/api/receipts/3/image");
  const imageLink = image.closest("a");
  expect(imageLink).toHaveAttribute("href", "/api/receipts/3/image");
  expect(imageLink).toHaveAttribute("target", "_blank");

  const rows = await lineRows();
  expect(rows.map((row) => within(row).getAllByRole("textbox").map(inputValue))).toEqual([
    ["Maito", "1,25"],
    ["Limu", "2,24"],
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
  expect(within(refundRow!).getByRole("textbox", { name: "Summa: Panttipalautus" })).toHaveValue(
    "-0,40",
  );

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
  // Missing fields are empty inputs since line editing (line-editing PC12).
  for (const label of ["Kauppa", "Päivä", "Loppusumma"]) {
    expect(screen.getByLabelText(label)).toHaveValue("");
  }
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

it("AC29: categories that cannot be loaded show the categories as text", async () => {
  server.use(
    http.get("/api/receipts/3", () => HttpResponse.json(RECEIPT_A)),
    http.get("/api/categories", () => HttpResponse.error()),
  );
  render(<ReceiptPage id={3} onBack={() => {}} />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Taustapalveluun ei saada yhteyttä.");
  // A disabled dropdown became the category as text (line-editing PC15).
  const [milkRow] = await lineRows();
  expect(within(milkRow!).getByText("Ruoka > Maitotuotteet")).toBeInTheDocument();
  expect(screen.queryByRole("combobox", { name: "Kategoria: Maito" })).toBeNull();
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
  // Controls stay usable while the answer waits; the save queue keeps the order
  // (line-editing PC12).
  expect(screen.getByRole("combobox", { name: "Kategoria: Maito" })).toBeEnabled();
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
  ).toEqual(["Tuote", "Summa", "Pantinpalautus", "Kategoria", ""]);
  for (const label of ["Kauppa", "Päivä", "Loppusumma"]) {
    expect(screen.getByText(label, { selector: "label" })).toBeInTheDocument();
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

// Line editing (T19-T21).

/** The receipt the backend would answer for a write, without recomputing the sums. */
function echo(receipt: Receipt) {
  return (write: RecordedWrite) => {
    const body = write.body as Record<string, unknown>;
    const lineMatch = /\/lines\/(\d+)$/.exec(write.path);
    if (write.method === "DELETE") {
      const lineId = Number(lineMatch?.[1]);
      return HttpResponse.json({ ...receipt, lines: receipt.lines.filter((l) => l.id !== lineId) });
    }
    if (write.method === "POST") {
      const added = {
        ...line(199, String(body.name), Number(body.amount_cents), null, null),
        ...body,
      };
      return HttpResponse.json({ ...receipt, lines: [...receipt.lines, added] });
    }
    if (lineMatch) {
      const lineId = Number(lineMatch[1]);
      return HttpResponse.json({
        ...receipt,
        lines: receipt.lines.map((l) => (l.id === lineId ? { ...l, ...body } : l)),
      });
    }
    return HttpResponse.json({ ...receipt, ...body });
  };
}

function refused(error: string, message: string) {
  return HttpResponse.json({ error, message }, { status: 422 });
}

const RECEIPT_A_REFUND: Receipt = {
  ...RECEIPT_A,
  lines: [...RECEIPT_A.lines, line(104, "Panttipalautus", -40, null, null, true)],
};

it("line-editing AC24: the receipt page shows editable fields", async () => {
  answers(RECEIPT_A_REFUND);
  render(<ReceiptPage id={3} onBack={() => {}} />);

  expect(await screen.findByLabelText("Kauppa")).toHaveValue("Testikauppa");
  expect(screen.getByLabelText("Päivä")).toHaveValue("2026-10-05");
  expect(screen.getByLabelText("Loppusumma")).toHaveValue("3,49");
  expect(screen.getByRole("textbox", { name: "Tuote: Maito" })).toHaveValue("Maito");
  expect(screen.getByRole("textbox", { name: "Summa: Maito" })).toHaveValue("1,25");
  expect(screen.getByRole("checkbox", { name: "Pantinpalautus: Maito" })).not.toBeChecked();
  expect(screen.getByRole("checkbox", { name: "Pantinpalautus: Panttipalautus" })).toBeChecked();
  expect(screen.getByRole("textbox", { name: "Summa: Panttipalautus" })).toHaveValue("-0,40");
  const rows = await lineRows();
  expect(within(rows[2]!).getByText("Pantinpalautus")).toBeInTheDocument();
  for (const row of rows) {
    expect(within(row).getByRole("button", { name: "Poista" })).toBeInTheDocument();
  }
  expect(screen.getByRole("heading", { name: "Uusi rivi" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Lisää rivi" })).toBeInTheDocument();
});

it("line-editing AC34: categories show as text while they load", async () => {
  let release: () => void = () => {};
  server.use(
    http.get("/api/receipts/3", () =>
      HttpResponse.json({
        ...RECEIPT_A,
        lines: [...RECEIPT_A.lines, line(103, "Outo", 50, null, null)],
      }),
    ),
    http.get("/api/categories", async () => {
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      return HttpResponse.json(ITEMS);
    }),
  );
  render(<ReceiptPage id={3} onBack={() => {}} />);

  const rows = await lineRows();
  expect(within(rows[0]!).getByText("Ruoka > Maitotuotteet")).toBeInTheDocument();
  expect(within(rows[1]!).getByText("Juomat")).toBeInTheDocument();
  expect(within(rows[2]!).getByText("–")).toBeInTheDocument();
  expect(screen.queryByRole("combobox")).toBeNull();

  release();

  expect(await screen.findByRole("combobox", { name: "Kategoria: Maito" })).toBeInTheDocument();
});

it("line-editing AC35: a receipt without lines can get a line", async () => {
  answers(RECEIPT_OLD);
  recordWrites(echo(RECEIPT_OLD));
  const user = userEvent.setup();
  render(<ReceiptPage id={6} onBack={() => {}} />);

  expect(await screen.findByText("Kuitilta ei luettu rivejä.")).toBeInTheDocument();
  const form = within(screen.getByRole("form", { name: "Uusi rivi" }));
  await user.type(form.getByLabelText("Tuote"), "Banaani");
  await user.type(form.getByLabelText("Summa"), "0,99");
  await user.click(form.getByRole("button", { name: "Lisää rivi" }));

  expect(await screen.findByRole("table", { name: "Kuittirivit" })).toBeInTheDocument();
  expect(screen.queryByText("Kuitilta ei luettu rivejä.")).toBeNull();
});

it("line-editing AC25: a name saves on Tab and Enter; Esc and unchanged fields send nothing", async () => {
  answers(RECEIPT_A);
  const writes = recordWrites((write) =>
    HttpResponse.json({
      ...RECEIPT_A,
      lines: [
        RECEIPT_A.lines[0],
        { ...line(102, "Limu", 224, DRINKS, "user"), ...(write.body as object) },
      ],
    }),
  );
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);
  const soda = await screen.findByRole("textbox", { name: "Tuote: Limu" });

  await user.clear(soda);
  await user.type(soda, "Kivennäisvesi");
  await user.tab();
  await waitFor(() => expect(screen.queryByText("ehdotus")).toBeNull());
  const renamed = screen.getByRole("textbox", { name: "Tuote: Kivennäisvesi" });
  await user.clear(renamed);
  await user.type(renamed, "Vesi{Enter}");
  const water = await screen.findByRole("textbox", { name: "Tuote: Vesi" });
  await user.type(water, "X{Escape}");
  await user.click(screen.getByRole("textbox", { name: "Tuote: Maito" }));
  await user.tab();

  expect(water).toHaveValue("Vesi");
  expect(writes.map((write) => [write.path, write.body])).toEqual([
    ["/api/receipts/3/lines/102", { name: "Kivennäisvesi" }],
    ["/api/receipts/3/lines/102", { name: "Vesi" }],
  ]);
});

it("line-editing AC26: amounts are read from the field, or refused without a request", async () => {
  answers(RECEIPT_A);
  const writes = recordWrites(() => HttpResponse.json(RECEIPT_A));
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);
  const amount = await screen.findByRole("textbox", { name: "Summa: Limu" });

  for (const text of ["3,00", "3.5", " -0,40 ", "3"]) {
    await user.clear(amount);
    await user.type(amount, text);
    await user.tab();
    await waitFor(() => expect(amount).toHaveValue("2,24"));
  }
  const [, sodaRow] = await lineRows();
  for (const text of ["abc", "1,234", "1 234,00", ""]) {
    await user.clear(amount);
    if (text) {
      await user.type(amount, text);
    }
    await user.tab();
    expect(await within(sodaRow!).findByRole("alert")).toHaveTextContent(
      "Anna summa muodossa 1,25.",
    );
  }

  expect(writes.map((write) => write.body)).toEqual([
    { amount_cents: 300 },
    { amount_cents: 350 },
    { amount_cents: -40 },
    { amount_cents: 300 },
  ]);
});

it("line-editing AC28: the deposit refund checkbox saves at once", async () => {
  answers(RECEIPT_A);
  const writes = recordWrites(echo(RECEIPT_A));
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);
  const amount = await screen.findByRole("textbox", { name: "Summa: Limu" });

  await user.clear(amount);
  await user.type(amount, "-0,40");
  await user.tab();
  await waitFor(() => expect(amount).toHaveValue("-0,40"));
  await user.click(screen.getByRole("checkbox", { name: "Pantinpalautus: Limu" }));

  const [, sodaRow] = await lineRows();
  expect(await within(sodaRow!).findByText("Pantinpalautus")).toBeInTheDocument();
  expect(within(sodaRow!).queryByRole("combobox")).toBeNull();
  expect(writes.map((write) => write.body)).toEqual([
    { amount_cents: -40 },
    { is_deposit_refund: true },
  ]);
});

it("line-editing AC29: store, date and total save from the view", async () => {
  answers(RECEIPT_A);
  const writes = recordWrites((write) => {
    const body = write.body as Record<string, unknown>;
    return HttpResponse.json(
      body.total_cents === 400
        ? { ...RECEIPT_A, total_cents: 400, difference_cents: 51, warning: true }
        : { ...RECEIPT_A, ...body },
    );
  });
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);
  const total = await screen.findByLabelText("Loppusumma");

  await user.clear(total);
  await user.type(total, "4,00{Enter}");
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Rivien summa 3,49 € poikkeaa loppusummasta 4,00 €. Erotus 0,51 €.",
  );
  const date = screen.getByLabelText("Päivä");
  fireEvent.change(date, { target: { value: "2026-10-06" } });
  fireEvent.blur(date);
  await waitFor(() => expect(writes).toHaveLength(2));
  const store = screen.getByLabelText("Kauppa");
  await user.clear(store);
  await user.type(store, "Uusi kauppa");
  await user.tab();

  await waitFor(() => expect(writes).toHaveLength(3));
  expect(writes.map((write) => [write.path, write.body])).toEqual([
    ["/api/receipts/3", { total_cents: 400 }],
    ["/api/receipts/3", { purchase_date: "2026-10-06" }],
    ["/api/receipts/3", { store: "Uusi kauppa" }],
  ]);
});

it("line-editing AC30: adding a line in the view", async () => {
  answers(RECEIPT_A);
  const writes = recordWrites(echo(RECEIPT_A));
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);
  const form = within(await screen.findByRole("form", { name: "Uusi rivi" }));

  await user.type(form.getByLabelText("Summa"), "x");
  await user.click(form.getByRole("button", { name: "Lisää rivi" }));
  expect(form.getByRole("alert")).toHaveTextContent("Anna summa muodossa 1,25.");
  await user.type(form.getByLabelText("Tuote"), "Banaani");
  await user.clear(form.getByLabelText("Summa"));
  await user.type(form.getByLabelText("Summa"), "0,99");
  await user.click(form.getByRole("button", { name: "Lisää rivi" }));

  expect(await screen.findByRole("textbox", { name: "Tuote: Banaani" })).toHaveValue("Banaani");
  expect(screen.getByRole("textbox", { name: "Summa: Banaani" })).toHaveValue("0,99");
  expect(form.getByLabelText("Tuote")).toHaveValue("");
  expect(writes).toEqual([
    {
      method: "POST",
      path: "/api/receipts/3/lines",
      body: { name: "Banaani", amount_cents: 99, is_deposit_refund: false },
    },
  ]);
});

it("line-editing AC31: deleting a line asks first", async () => {
  answers(RECEIPT_A);
  const writes = recordWrites(() =>
    HttpResponse.json({ ...RECEIPT_A, lines: [RECEIPT_A.lines[0]], line_sum_cents: 125 }),
  );
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);
  const [, sodaRow] = await lineRows();

  await user.click(within(sodaRow!).getByRole("button", { name: "Poista" }));
  await user.click(within(sodaRow!).getByRole("button", { name: "Peruuta" }));
  expect(writes).toEqual([]);
  await user.click(within(sodaRow!).getByRole("button", { name: "Poista" }));
  await user.click(within(sodaRow!).getByRole("button", { name: "Poista" }));

  expect(await screen.findByText("Rivien summa 1,25 €")).toBeInTheDocument();
  expect(await lineRows()).toHaveLength(1);
  expect(writes).toEqual([{ method: "DELETE", path: "/api/receipts/3/lines/102", body: null }]);
});

it("line-editing AC32: saves are sent one at a time and keep the focus", async () => {
  answers(RECEIPT_A);
  const renamed: Receipt = {
    ...RECEIPT_A,
    lines: RECEIPT_A.lines.map((l) => (l.id === 102 ? { ...l, name: "Vesi" } : l)),
  };
  let release: () => void = () => {};
  const writes = recordWrites(async (write) => {
    if (writes.length === 1) {
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      return echo(RECEIPT_A)(write);
    }
    return echo(renamed)(write);
  });
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);
  const soda = await screen.findByRole("textbox", { name: "Tuote: Limu" });

  await user.clear(soda);
  await user.type(soda, "Vesi");
  await user.tab();
  const milkAmount = screen.getByRole("textbox", { name: "Summa: Maito" });
  await user.click(milkAmount);
  await user.clear(milkAmount);
  await user.type(milkAmount, "2,00");
  await user.click(screen.getByRole("textbox", { name: "Tuote: Maito" }));

  expect(screen.getByRole("textbox", { name: "Tuote: Maito" })).toHaveFocus();
  await waitFor(() => expect(writes).toHaveLength(1));
  release();
  await waitFor(() => expect(writes).toHaveLength(2));
  expect(writes.map((write) => [write.path, write.body])).toEqual([
    ["/api/receipts/3/lines/102", { name: "Vesi" }],
    ["/api/receipts/3/lines/101", { amount_cents: 200 }],
  ]);
  expect(await screen.findByRole("textbox", { name: "Tuote: Vesi" })).toHaveValue("Vesi");
  expect(screen.getByRole("textbox", { name: "Summa: Maito" })).toHaveValue("2,00");
});

it("line-editing AC33: errors show by their field and keep or restore the values", async () => {
  answers(RECEIPT_A);
  recordWrites((write) => {
    const body = write.body as Record<string, unknown>;
    if (write.method === "PATCH" && body.name === "") {
      return refused("invalid_name", "Nimen pituuden on oltava 1–100 merkkiä.");
    }
    if (write.method === "PATCH" && "is_deposit_refund" in body) {
      return refused("deposit_refund_amount", "Pantinpalautuksen summan on oltava negatiivinen.");
    }
    return HttpResponse.error();
  });
  const user = userEvent.setup();
  render(<ReceiptPage id={3} onBack={() => {}} />);
  const soda = await screen.findByRole("textbox", { name: "Tuote: Limu" });
  const [, sodaRow] = await lineRows();

  await user.clear(soda);
  await user.tab();
  expect(
    await within(sodaRow!).findByText("Nimen pituuden on oltava 1–100 merkkiä."),
  ).toBeInTheDocument();
  expect(soda).toHaveValue("");

  const refund = screen.getByRole("checkbox", { name: "Pantinpalautus: Limu" });
  await user.click(refund);
  expect(
    await within(sodaRow!).findByText("Pantinpalautuksen summan on oltava negatiivinen."),
  ).toBeInTheDocument();
  expect(refund).not.toBeChecked();

  await user.click(within(sodaRow!).getByRole("button", { name: "Poista" }));
  await user.click(within(sodaRow!).getByRole("button", { name: "Poista" }));
  expect(
    await within(sodaRow!).findByText("Taustapalveluun ei saada yhteyttä."),
  ).toBeInTheDocument();
  expect(await lineRows()).toHaveLength(2);

  const form = within(screen.getByRole("form", { name: "Uusi rivi" }));
  await user.type(form.getByLabelText("Tuote"), "Banaani");
  await user.type(form.getByLabelText("Summa"), "0,99");
  await user.click(form.getByRole("button", { name: "Lisää rivi" }));
  expect(await form.findByRole("alert")).toHaveTextContent("Taustapalveluun ei saada yhteyttä.");
  expect(form.getByLabelText("Tuote")).toHaveValue("Banaani");

  await user.type(soda, "{Escape}");
  expect(soda).toHaveValue("Limu");
  expect(within(sodaRow!).queryByText("Nimen pituuden on oltava 1–100 merkkiä.")).toBeNull();
});
