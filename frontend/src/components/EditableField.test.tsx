import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  expect(field).toHaveAttribute("type", "text");
  expect(field).toHaveValue("05.10.2026");
  expect(screen.getByText("Päivä", { selector: "label" })).toBeInTheDocument();
});

// Date field PC2, PC4.

/** A date field with its saved value kept the way the receipt page keeps it. */
function SavedDate({
  initial,
  answer,
}: {
  initial: string;
  answer: (date: string) => Promise<string | null>;
}) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <EditableField
        label="Päivä"
        showLabel
        type="date"
        value={value}
        onSave={async (date) => {
          const message = await answer(date);
          if (message === null) {
            setValue(date);
          }
          return message;
        }}
      />
      <button type="button">next</button>
    </>
  );
}

function renderDate(initial: string, answer = vi.fn(() => Promise.resolve<string | null>(null))) {
  render(<SavedDate initial={initial} answer={answer} />);
  return { answer, field: screen.getByLabelText("Päivä") };
}

const next = () => userEvent.click(screen.getByRole("button", { name: "next" }));

it("date-field AC2: a typed date is saved as YYYY-MM-DD and shown with leading zeros", async () => {
  const { answer, field } = renderDate("");

  await userEvent.type(field, " 5.10.2026 ");
  await next();

  expect(answer).toHaveBeenCalledExactlyOnceWith("2026-10-05");
  expect(field).toHaveValue("05.10.2026");
});

it("date-field AC4: invalid text keeps the text, shows the message and saves nothing", async () => {
  const { answer, field } = renderDate("");

  await userEvent.type(field, "30.02.2026");
  await next();

  expect(answer).not.toHaveBeenCalled();
  expect(field).toHaveValue("30.02.2026");
  expect(screen.getByRole("alert")).toHaveTextContent("Päivämäärä ei kelpaa.");
});

it("date-field AC5: editing the text clears the message", async () => {
  const { field } = renderDate("");

  await userEvent.type(field, "abc");
  await next();
  await userEvent.type(field, "d");

  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("date-field AC7: a day picked from the calendar is saved once", async () => {
  const { answer, field } = renderDate("2026-10-05");
  const picker = document.querySelector<HTMLInputElement>('input[type="date"]');
  if (picker === null) {
    throw new Error("no picker");
  }

  fireEvent.change(picker, { target: { value: "2026-10-07" } });

  await waitFor(() => expect(field).toHaveValue("07.10.2026"));
  expect(answer).toHaveBeenCalledExactlyOnceWith("2026-10-07");
});

it("date-field AC8: Enter and then leaving save once", async () => {
  const { answer, field } = renderDate("2026-10-05");

  await userEvent.clear(field);
  await userEvent.type(field, "06.10.2026{Enter}");
  await next();

  expect(answer).toHaveBeenCalledExactlyOnceWith("2026-10-06");
  expect(field).toHaveValue("06.10.2026");
});

it("date-field AC9: the same day in another form saves nothing", async () => {
  const { answer, field } = renderDate("2026-10-05");

  await userEvent.clear(field);
  await userEvent.type(field, "5.10.2026");
  await next();

  expect(answer).not.toHaveBeenCalled();
  expect(field).toHaveValue("05.10.2026");
});

it("date-field AC10: Esc puts back the saved date and clears the message", async () => {
  const { answer, field } = renderDate("2026-10-05");

  await userEvent.clear(field);
  await userEvent.type(field, "30.02.2026{Enter}");
  expect(screen.getByRole("alert")).toBeInTheDocument();
  await userEvent.type(field, "{Escape}");

  expect(field).toHaveValue("05.10.2026");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(answer).not.toHaveBeenCalled();
});

it("date-field AC11: emptying a saved date shows the message and saves nothing", async () => {
  const { answer, field } = renderDate("2026-10-05");

  await userEvent.clear(field);
  await next();

  expect(answer).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toHaveTextContent("Päivämäärä ei kelpaa.");
});

it("date-field AC12: moving through an empty date does nothing", async () => {
  const { answer, field } = renderDate("");

  await userEvent.click(field);
  await next();

  expect(answer).not.toHaveBeenCalled();
  expect(field).toHaveValue("");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("date-field AC13: a refused save keeps the text and shows the answer", async () => {
  const answer = vi.fn(() => Promise.resolve<string | null>("Päivämäärä ei kelpaa."));
  const { field } = renderDate("2026-10-05", answer);

  await userEvent.clear(field);
  await userEvent.type(field, "06.10.2026");
  await next();

  expect(field).toHaveValue("06.10.2026");
  expect(screen.getByRole("alert")).toHaveTextContent("Päivämäärä ei kelpaa.");
});

function calendar(): HTMLInputElement {
  const picker = document.querySelector<HTMLInputElement>('input[type="date"]');
  if (picker === null) {
    throw new Error("no picker");
  }
  return picker;
}

it("date-field AC8: leaving the field while a save waits does not save again", async () => {
  let finish: (message: string | null) => void = () => {};
  const answer = vi.fn(
    () =>
      new Promise<string | null>((resolve) => {
        finish = resolve;
      }),
  );
  const { field } = renderDate("2026-10-05", answer);

  await userEvent.clear(field);
  await userEvent.type(field, "06.10.2026{Enter}");
  await next();
  expect(answer).toHaveBeenCalledExactlyOnceWith("2026-10-06");

  act(() => finish(null));
  await waitFor(() => expect(answer).toHaveBeenCalledOnce());
  expect(field).toHaveValue("06.10.2026");
});

it("date-field AC13: a refused pick keeps the picked day", async () => {
  const answer = vi.fn(() => Promise.resolve<string | null>("Päivämäärä ei kelpaa."));
  const { field } = renderDate("2026-10-05", answer);

  fireEvent.change(calendar(), { target: { value: "2026-10-07" } });

  expect(await screen.findByRole("alert")).toHaveTextContent("Päivämäärä ei kelpaa.");
  expect(field).toHaveValue("07.10.2026");
});

it("date-field PC2: picking the saved day clears the message", async () => {
  const { answer, field } = renderDate("2026-10-05");

  await userEvent.clear(field);
  await userEvent.type(field, "abc{Enter}");
  expect(screen.getByRole("alert")).toBeInTheDocument();
  fireEvent.change(calendar(), { target: { value: "2026-10-05" } });

  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  expect(field).toHaveValue("05.10.2026");
  expect(answer).not.toHaveBeenCalled();
});

it("date-field AC17: moving inside the calendar saves nothing", () => {
  const { answer, field } = renderDate("2026-10-05");

  fireEvent.input(calendar(), { target: { value: "2026-10-06" } });

  expect(answer).not.toHaveBeenCalled();
  expect(field).toHaveValue("05.10.2026");
});
