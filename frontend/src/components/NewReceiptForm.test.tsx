import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, it, vi } from "vitest";
import { FAILED_IMAGES, RECEIPT_MANUAL } from "../test/receipts";
import { server } from "../test/server";
import { NewReceiptForm } from "./NewReceiptForm";

/** Answer the failed images list, and record each create body. */
function answers(
  create: () => Response = () => HttpResponse.json(RECEIPT_MANUAL, { status: 201 }),
) {
  const bodies: unknown[] = [];
  server.use(
    http.get("/api/failed-images", () => HttpResponse.json({ file_names: FAILED_IMAGES })),
    http.post("/api/receipts", async ({ request }) => {
      bodies.push(await request.json());
      return create();
    }),
  );
  return bodies;
}

function optionTexts(select: HTMLElement): string[] {
  return within(select)
    .getAllByRole("option")
    .map((option) => option.textContent ?? "");
}

async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Kauppa"), "Testikauppa");
  fireEvent.change(screen.getByLabelText("Päivä"), { target: { value: "2026-10-05" } });
  await user.type(screen.getByLabelText("Loppusumma"), "3,49");
}

it("receipt-management AC29: creates a receipt without an image", async () => {
  const bodies = answers();
  const onCreated = vi.fn();
  const user = userEvent.setup();
  render(<NewReceiptForm onCreated={onCreated} onCancel={() => {}} />);

  expect(screen.getByRole("form", { name: "Uusi kuitti" })).toBeInTheDocument();
  await fill(user);
  await user.click(screen.getByRole("button", { name: "Luo kuitti" }));

  await waitFor(() => expect(onCreated).toHaveBeenCalledWith(RECEIPT_MANUAL.id));
  expect(bodies).toEqual([{ store: "Testikauppa", purchase_date: "2026-10-05", total_cents: 349 }]);
});

it("receipt-management AC30: offers the failed images and previews the chosen one", async () => {
  const bodies = answers();
  const user = userEvent.setup();
  render(<NewReceiptForm onCreated={() => {}} onCancel={() => {}} />);
  const select = screen.getByLabelText("Kuva");

  await waitFor(() =>
    expect(optionTexts(select)).toEqual(["Ei kuvaa", "b.png", "fake.jpg", "IMG_2.jpg"]),
  );
  expect(select).toHaveDisplayValue("Ei kuvaa");
  expect(screen.queryByRole("img")).toBeNull();
  await user.selectOptions(select, "IMG_2.jpg");

  expect(screen.getByRole("img", { name: "Valittu kuva" })).toHaveAttribute(
    "src",
    "/api/failed-images/image?name=IMG_2.jpg",
  );
  await fill(user);
  await user.click(screen.getByRole("button", { name: "Luo kuitti" }));
  await waitFor(() => expect(bodies).toHaveLength(1));
  expect(bodies[0]).toEqual({
    store: "Testikauppa",
    purchase_date: "2026-10-05",
    total_cents: 349,
    image_file_name: "IMG_2.jpg",
  });

  await user.selectOptions(select, "Ei kuvaa");
  expect(screen.queryByRole("img")).toBeNull();
});

it("receipt-management AC31: a preview that does not load shows a text", async () => {
  answers();
  const user = userEvent.setup();
  render(<NewReceiptForm onCreated={() => {}} onCancel={() => {}} />);
  const select = screen.getByLabelText("Kuva");
  await waitFor(() => expect(optionTexts(select)).toHaveLength(4));

  await user.selectOptions(select, "b.png");
  fireEvent.error(screen.getByRole("img", { name: "Valittu kuva" }));

  expect(screen.getByText("Kuvaa ei voitu näyttää.")).toBeInTheDocument();
  expect(screen.queryByRole("img")).toBeNull();
  await user.selectOptions(select, "IMG_2.jpg");
  expect(screen.getByRole("img", { name: "Valittu kuva" })).toBeInTheDocument();
});

it("receipt-management AC31: a failed list still lets the receipt be created", async () => {
  const bodies = answers();
  server.use(
    http.get("/api/failed-images", () =>
      HttpResponse.json(
        {
          error: "folders_unavailable",
          message: "Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.",
        },
        { status: 503 },
      ),
    ),
  );
  const onCreated = vi.fn();
  const user = userEvent.setup();
  render(<NewReceiptForm onCreated={onCreated} onCancel={() => {}} />);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.",
  );
  expect(optionTexts(screen.getByLabelText("Kuva"))).toEqual(["Ei kuvaa"]);
  await fill(user);
  await user.click(screen.getByRole("button", { name: "Luo kuitti" }));

  await waitFor(() => expect(onCreated).toHaveBeenCalledWith(RECEIPT_MANUAL.id));
  expect(bodies).toHaveLength(1);
});

it("receipt-management AC32: an empty date and an unreadable total are not sent", async () => {
  const bodies = answers();
  const user = userEvent.setup();
  render(<NewReceiptForm onCreated={() => {}} onCancel={() => {}} />);

  await user.type(screen.getByLabelText("Loppusumma"), "abc");
  await user.click(screen.getByRole("button", { name: "Luo kuitti" }));

  const alerts = await screen.findAllByRole("alert");
  expect(alerts.map((alert) => alert.textContent?.trim())).toEqual([
    "Anna päivämäärä.",
    "Anna summa muodossa 1,25.",
  ]);
  expect(bodies).toEqual([]);
});

it.each([
  [
    "a refusal",
    () =>
      HttpResponse.json(
        { error: "duplicate_image", message: "Kuva on jo tuotu toiseen kuittiin." },
        { status: 409 },
      ),
    "Kuva on jo tuotu toiseen kuittiin.",
  ],
  ["a network error", () => HttpResponse.error(), "Taustapalveluun ei saada yhteyttä."],
])("receipt-management AC33: %s keeps the form and its values", async (_, create, text) => {
  answers(create);
  const onCreated = vi.fn();
  const user = userEvent.setup();
  render(<NewReceiptForm onCreated={onCreated} onCancel={() => {}} />);
  const select = screen.getByLabelText("Kuva");
  await waitFor(() => expect(optionTexts(select)).toHaveLength(4));
  await user.selectOptions(select, "IMG_2.jpg");
  await fill(user);

  await user.click(screen.getByRole("button", { name: "Luo kuitti" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(text);
  expect(onCreated).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Kauppa")).toHaveValue("Testikauppa");
  expect(screen.getByLabelText("Päivä")).toHaveValue("2026-10-05");
  expect(screen.getByLabelText("Loppusumma")).toHaveValue("3,49");
  expect(select).toHaveDisplayValue("IMG_2.jpg");
  expect(screen.getByRole("img", { name: "Valittu kuva" })).toBeInTheDocument();
});

it("receipt-management AC34: cancel sends nothing", async () => {
  const bodies = answers();
  const onCancel = vi.fn();
  const user = userEvent.setup();
  render(<NewReceiptForm onCreated={() => {}} onCancel={onCancel} />);
  await fill(user);

  await user.click(screen.getByRole("button", { name: "Peruuta" }));

  expect(onCancel).toHaveBeenCalledTimes(1);
  expect(bodies).toEqual([]);
});

it("receipt-management AC36: a double click sends one create; a refusal enables it again", async () => {
  let release = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const bodies = answers();
  server.use(
    http.post("/api/receipts", async ({ request }) => {
      bodies.push(await request.json());
      await held;
      return HttpResponse.json(
        { error: "duplicate_image", message: "Kuva on jo tuotu toiseen kuittiin." },
        { status: 409 },
      );
    }),
  );
  const user = userEvent.setup();
  render(<NewReceiptForm onCreated={() => {}} onCancel={() => {}} />);
  await fill(user);
  const button = screen.getByRole("button", { name: "Luo kuitti" });

  await user.dblClick(button);

  await waitFor(() => expect(bodies).toHaveLength(1));
  expect(button).toBeDisabled();
  release();
  expect(await screen.findByRole("alert")).toHaveTextContent("Kuva on jo tuotu toiseen kuittiin.");
  expect(button).toBeEnabled();
  expect(bodies).toHaveLength(1);
});
