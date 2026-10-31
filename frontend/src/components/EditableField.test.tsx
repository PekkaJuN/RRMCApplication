import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, it, vi } from "vitest";
import { EditableField } from "./EditableField";

/** The field with its saved value kept the way the receipt page keeps it. */
function Saved({
  initial,
  answer,
}: {
  initial: string;
  answer: (text: string) => Promise<string | null>;
}) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <EditableField
        label="Tuote: Limu"
        value={value}
        onSave={async (text) => {
          const message = await answer(text);
          if (message === null) {
            setValue(text);
          }
          return message;
        }}
      />
      <button type="button">next</button>
    </>
  );
}

it("line-editing AC25: saves on Tab and on Enter, once, only when changed", async () => {
  const answer = vi.fn(() => Promise.resolve(null));
  const user = userEvent.setup();
  render(<Saved initial="Limu" answer={answer} />);
  const field = screen.getByRole("textbox", { name: "Tuote: Limu" });

  await user.click(field);
  await user.tab();
  expect(answer).not.toHaveBeenCalled();

  await user.clear(field);
  await user.type(field, "Kivennäisvesi");
  await user.tab();
  await user.clear(field);
  await user.type(field, "Vesi{Enter}");
  await user.tab();

  expect(answer.mock.calls).toEqual([["Kivennäisvesi"], ["Vesi"]]);
  expect(field).toHaveValue("Vesi");
});

it("line-editing AC25: Esc puts back the saved value without saving", async () => {
  const answer = vi.fn(() => Promise.resolve(null));
  const user = userEvent.setup();
  render(<Saved initial="Vesi" answer={answer} />);
  const field = screen.getByRole("textbox", { name: "Tuote: Limu" });

  await user.type(field, "X{Escape}");
  await user.tab();

  expect(field).toHaveValue("Vesi");
  expect(answer).not.toHaveBeenCalled();
});

it("line-editing AC33: a refused save shows the message and keeps the typed text", async () => {
  const answer = vi.fn((text: string) =>
    Promise.resolve(text === "" ? "Nimen pituuden on oltava 1–100 merkkiä." : null),
  );
  const user = userEvent.setup();
  render(<Saved initial="Limu" answer={answer} />);
  const field = screen.getByRole("textbox", { name: "Tuote: Limu" });

  await user.clear(field);
  await user.tab();

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Nimen pituuden on oltava 1–100 merkkiä.",
  );
  expect(field).toHaveValue("");

  await user.type(field, "{Escape}");
  expect(field).toHaveValue("Limu");
  expect(screen.queryByRole("alert")).toBeNull();
});

it("line-editing AC33: the message clears on the next successful save", async () => {
  const answer = vi.fn((text: string) => Promise.resolve(text === "" ? "Virhe." : null));
  const user = userEvent.setup();
  render(<Saved initial="Limu" answer={answer} />);
  const field = screen.getByRole("textbox", { name: "Tuote: Limu" });

  await user.clear(field);
  await user.tab();
  expect(await screen.findByRole("alert")).toHaveTextContent("Virhe.");
  await user.type(field, "Vesi");
  await user.tab();

  expect(screen.queryByRole("alert")).toBeNull();
  expect(field).toHaveValue("Vesi");
});

it("line-editing AC32: text typed while a save waits is kept when the answer arrives", async () => {
  let release: (message: string | null) => void = () => {};
  const answer = vi.fn(
    (text: string) =>
      new Promise<string | null>((resolve) => {
        release = text === "Vesi" ? resolve : () => {};
        if (text !== "Vesi") resolve(null);
      }),
  );
  const user = userEvent.setup();
  render(<Saved initial="Limu" answer={answer} />);
  const field = screen.getByRole("textbox", { name: "Tuote: Limu" });

  await user.clear(field);
  await user.type(field, "Vesi{Enter}2");
  release(null);
  await screen.findByDisplayValue("Vesi2");
  await user.tab();

  expect(answer.mock.calls).toEqual([["Vesi"], ["Vesi2"]]);
  expect(field).toHaveValue("Vesi2");
});

it("line-editing AC25: a new saved value shows when nothing is typed", () => {
  const onSave = () => Promise.resolve(null);
  const { rerender } = render(<EditableField label="Kauppa" value="A" onSave={onSave} />);

  rerender(<EditableField label="Kauppa" value="B" onSave={onSave} />);

  expect(screen.getByRole("textbox", { name: "Kauppa" })).toHaveValue("B");
});

it("line-editing AC24: a field with a visible label and a date field", () => {
  const onSave = () => Promise.resolve(null);
  render(<EditableField label="Päivä" value="2026-10-05" type="date" showLabel onSave={onSave} />);

  const field = screen.getByLabelText("Päivä");
  expect(field).toHaveAttribute("type", "date");
  expect(field).toHaveValue("2026-10-05");
  expect(screen.getByText("Päivä", { selector: "label" })).toBeInTheDocument();
});
