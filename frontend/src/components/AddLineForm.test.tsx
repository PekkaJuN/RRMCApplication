import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { AddLineForm } from "./AddLineForm";

function form() {
  return within(screen.getByRole("form", { name: "Uusi rivi" }));
}

it("line-editing AC30: adds a line and empties the form", async () => {
  const onAdd = vi.fn(() => Promise.resolve(null));
  const user = userEvent.setup();
  render(<AddLineForm onAdd={onAdd} />);

  expect(screen.getByRole("heading", { name: "Uusi rivi" })).toBeInTheDocument();
  await user.type(form().getByLabelText("Tuote"), "Banaani");
  await user.type(form().getByLabelText("Summa"), "0,99");
  await user.click(form().getByRole("button", { name: "Lisää rivi" }));

  expect(onAdd.mock.calls).toEqual([
    [{ name: "Banaani", amount_cents: 99, is_deposit_refund: false }],
  ]);
  expect(form().getByLabelText("Tuote")).toHaveValue("");
  expect(form().getByLabelText("Summa")).toHaveValue("");
  expect(form().getByLabelText("Pantinpalautus")).not.toBeChecked();
});

it("line-editing AC30: a deposit refund line", async () => {
  const onAdd = vi.fn(() => Promise.resolve(null));
  const user = userEvent.setup();
  render(<AddLineForm onAdd={onAdd} />);

  await user.type(form().getByLabelText("Tuote"), "Panttipalautus");
  await user.type(form().getByLabelText("Summa"), "-0,40");
  await user.click(form().getByLabelText("Pantinpalautus"));
  await user.click(form().getByRole("button", { name: "Lisää rivi" }));

  expect(onAdd.mock.calls).toEqual([
    [{ name: "Panttipalautus", amount_cents: -40, is_deposit_refund: true }],
  ]);
});

it("line-editing AC30: an amount that cannot be read is not sent", async () => {
  const onAdd = vi.fn(() => Promise.resolve(null));
  const user = userEvent.setup();
  render(<AddLineForm onAdd={onAdd} />);

  await user.type(form().getByLabelText("Tuote"), "Banaani");
  await user.type(form().getByLabelText("Summa"), "x");
  await user.click(form().getByRole("button", { name: "Lisää rivi" }));

  expect(onAdd).not.toHaveBeenCalled();
  expect(form().getByRole("alert")).toHaveTextContent("Anna summa muodossa 1,25.");
});

it("line-editing AC33: a refused add shows the message and keeps the values", async () => {
  const onAdd = vi.fn(() => Promise.resolve("Taustapalveluun ei saada yhteyttä."));
  const user = userEvent.setup();
  render(<AddLineForm onAdd={onAdd} />);

  await user.type(form().getByLabelText("Tuote"), "Banaani");
  await user.type(form().getByLabelText("Summa"), "0,99");
  await user.click(form().getByRole("button", { name: "Lisää rivi" }));

  expect(await form().findByRole("alert")).toHaveTextContent("Taustapalveluun ei saada yhteyttä.");
  expect(form().getByLabelText("Tuote")).toHaveValue("Banaani");
  expect(form().getByLabelText("Summa")).toHaveValue("0,99");
});
