import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDelete } from "./ConfirmDelete";

describe("ConfirmDelete", () => {
  it("AC28: the first click asks for confirmation in the page", async () => {
    const onConfirm = vi.fn();
    render(<ConfirmDelete onConfirm={onConfirm} />);

    await userEvent.click(screen.getByRole("button", { name: "Poista" }));

    expect(screen.getByText("Poistetaanko?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Peruuta" })).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("AC28: cancel does nothing and shows the delete button again", async () => {
    const onConfirm = vi.fn();
    render(<ConfirmDelete onConfirm={onConfirm} />);

    await userEvent.click(screen.getByRole("button", { name: "Poista" }));
    await userEvent.click(screen.getByRole("button", { name: "Peruuta" }));

    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.queryByText("Poistetaanko?")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Poista" })).toBeInTheDocument();
  });

  it("AC22: confirming calls the handler once", async () => {
    const onConfirm = vi.fn();
    render(<ConfirmDelete onConfirm={onConfirm} />);

    await userEvent.click(screen.getByRole("button", { name: "Poista" }));
    await userEvent.click(screen.getByRole("button", { name: "Poista" }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
