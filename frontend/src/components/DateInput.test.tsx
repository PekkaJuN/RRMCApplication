import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { DateInput } from "./DateInput";

const showPicker = vi.fn();

beforeEach(() => {
  // jsdom has no native calendar.
  HTMLInputElement.prototype.showPicker = showPicker;
});

afterEach(() => {
  showPicker.mockReset();
});

function renderInput(text: string, onPick = vi.fn()) {
  render(
    <DateInput
      id="date"
      label="Päivä"
      ariaLabel="Päivä"
      text={text}
      onTextChange={vi.fn()}
      onPick={onPick}
      onBlur={vi.fn()}
    />,
  );
  return onPick;
}

function picker(): HTMLInputElement {
  const element = document.querySelector<HTMLInputElement>('input[type="date"]');
  if (element === null) {
    throw new Error("no picker");
  }
  return element;
}

it("date-field PC1: the text field shows the text and the placeholder", () => {
  renderInput("05.10.2026");

  const field = screen.getByRole("textbox", { name: "Päivä" });
  expect(field).toHaveValue("05.10.2026");
  expect(field).toHaveAttribute("placeholder", "pp.kk.vvvv");
});

it("date-field AC6: the button opens the calendar on the field's date", async () => {
  renderInput("05.10.2026");

  await userEvent.click(screen.getByRole("button", { name: "Avaa kalenteri: Päivä" }));

  expect(showPicker).toHaveBeenCalledOnce();
  expect(picker()).toHaveValue("2026-10-05");
});

it("date-field AC6: the button works from the keyboard", async () => {
  renderInput("05.10.2026");

  await userEvent.tab();
  await userEvent.tab();
  expect(screen.getByRole("button", { name: "Avaa kalenteri: Päivä" })).toHaveFocus();
  await userEvent.keyboard("{Enter}");

  expect(showPicker).toHaveBeenCalledOnce();
});

it("date-field PC3: without a valid date the calendar has no date, so it opens on today", () => {
  renderInput("30.02.2026");

  expect(picker()).toHaveValue("");
});

it("date-field AC7: picking a day gives its text once", () => {
  const onPick = renderInput("05.10.2026");

  fireEvent.change(picker(), { target: { value: "2026-10-07" } });

  expect(onPick).toHaveBeenCalledOnce();
  expect(onPick).toHaveBeenCalledWith("07.10.2026");
});

it("date-field AC7: clearing the calendar gives nothing", () => {
  const onPick = renderInput("05.10.2026");

  fireEvent.change(picker(), { target: { value: "" } });

  expect(onPick).not.toHaveBeenCalled();
});

it("date-field PC7: the calendar input is out of the keyboard order and the accessibility tree", () => {
  renderInput("05.10.2026");

  expect(picker()).toHaveAttribute("tabindex", "-1");
  expect(picker()).toHaveAttribute("aria-hidden", "true");
});

it("date-field AC16: a calendar-only field cannot be typed in and opens on a click", async () => {
  const onTextChange = vi.fn();
  render(
    <DateInput
      id="date"
      label="Alkaen"
      ariaLabel="Alkaen"
      pickerOnly
      text="05.10.2026"
      onTextChange={onTextChange}
      onPick={vi.fn()}
      onBlur={vi.fn()}
    />,
  );
  const field = screen.getByRole("textbox", { name: "Alkaen" });

  await userEvent.type(field, "1");

  expect(onTextChange).not.toHaveBeenCalled();
  expect(field).toHaveValue("05.10.2026");
  expect(showPicker).toHaveBeenCalled();
  expect(picker()).toHaveValue("2026-10-05");
});

it("date-field AC17: moving inside the calendar gives nothing", () => {
  const onPick = renderInput("05.10.2026");

  fireEvent.input(picker(), { target: { value: "2026-10-06" } });

  expect(onPick).not.toHaveBeenCalled();
});

it("date-field AC7: the day the calendar stops on is given once", () => {
  const onPick = renderInput("05.10.2026");

  fireEvent.input(picker(), { target: { value: "2026-10-06" } });
  fireEvent.change(picker());

  expect(onPick).toHaveBeenCalledOnce();
  expect(onPick).toHaveBeenCalledWith("06.10.2026");
});

it("date-field PC3: the calendar follows the field", () => {
  const props = {
    id: "date",
    label: "Päivä",
    ariaLabel: "Päivä",
    onTextChange: vi.fn(),
    onPick: vi.fn(),
    onBlur: vi.fn(),
  };
  const { rerender } = render(<DateInput {...props} text="05.10.2026" />);

  rerender(<DateInput {...props} text="07.10.2026" />);

  expect(picker()).toHaveValue("2026-10-07");
});
