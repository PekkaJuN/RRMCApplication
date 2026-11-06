import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, it, vi } from "vitest";
import { answerBudget } from "../test/budget";
import { server } from "../test/server";
import { BudgetPage } from "./BudgetPage";

async function totalRow(): Promise<HTMLElement> {
  const table = await screen.findByRole("table", { name: "Budjetti" });
  return within(table).getByRole("row", { name: /Yhteensä/ });
}

it("budget AC17: shows a field per row and the total", async () => {
  answerBudget();
  render(<BudgetPage />);

  expect(await screen.findByRole("textbox", { name: "Ruoka" })).toHaveValue("400,00");
  expect(screen.getByRole("textbox", { name: "Auto" })).toHaveValue("0,00");
  expect(screen.getByRole("textbox", { name: "Juomat" })).toHaveValue("50,00");
  expect(await totalRow()).toHaveTextContent("450,00 €");
  expect(screen.getByRole("heading", { name: "Budjetti" })).toBeInTheDocument();
});

it("budget AC17: leaving a field saves the cents and updates the total", async () => {
  const saves = answerBudget();
  const user = userEvent.setup();
  render(<BudgetPage />);
  const field = await screen.findByRole("textbox", { name: "Auto" });

  await user.clear(field);
  await user.type(field, "150");
  await user.tab();

  expect(await screen.findByText("600,00 €")).toBeInTheDocument();
  expect(saves).toEqual([[7, 15000]]);
  expect(field).toHaveValue("150,00");
});

it("budget AC17: Enter saves", async () => {
  const saves = answerBudget();
  const user = userEvent.setup();
  render(<BudgetPage />);
  const field = await screen.findByRole("textbox", { name: "Auto" });

  await user.clear(field);
  await user.type(field, "150{Enter}");

  expect(await screen.findByText("600,00 €")).toBeInTheDocument();
  expect(saves).toEqual([[7, 15000]]);
});

it("budget AC32: a second save waits for the answer to the first", async () => {
  let release = () => {};
  const saves = answerBudget(new Promise((resolve) => (release = resolve)));
  const user = userEvent.setup();
  render(<BudgetPage />);
  const auto = await screen.findByRole("textbox", { name: "Auto" });
  const juomat = screen.getByRole("textbox", { name: "Juomat" });

  await user.clear(auto);
  await user.type(auto, "150");
  await user.tab();
  await vi.waitFor(() => expect(saves).toEqual([[7, 15000]]));
  await user.clear(juomat);
  await user.type(juomat, "60");
  await user.tab();
  // Time for a request that does not wait to reach MSW.
  await new Promise((resolve) => setTimeout(resolve, 100));

  expect(saves).toEqual([[7, 15000]]);

  release();

  await vi.waitFor(() =>
    expect(saves).toEqual([
      [7, 15000],
      [30, 6000],
    ]),
  );
  // 400,00 + 150,00 + 60,00
  expect(await screen.findByText("610,00 €")).toBeInTheDocument();
  expect(auto).toHaveValue("150,00");
  expect(juomat).toHaveValue("60,00");
});

it("budget AC32: a failed save does not stop the next one", async () => {
  answerBudget();
  let failures = 1;
  server.use(
    http.put("/api/budget/:id", () => {
      if (failures > 0) {
        failures -= 1;
        return HttpResponse.error();
      }
      return undefined;
    }),
  );
  const user = userEvent.setup();
  render(<BudgetPage />);
  const auto = await screen.findByRole("textbox", { name: "Auto" });

  await user.clear(auto);
  await user.type(auto, "150");
  await user.tab();
  await screen.findByRole("alert");
  const juomat = screen.getByRole("textbox", { name: "Juomat" });
  await user.clear(juomat);
  await user.type(juomat, "60");
  await user.tab();

  expect(await screen.findByText("460,00 €")).toBeInTheDocument();
});

it("budget AC18: text that is no amount shows an alert and sends nothing", async () => {
  const saves = answerBudget();
  const user = userEvent.setup();
  render(<BudgetPage />);
  const field = await screen.findByRole("textbox", { name: "Auto" });

  await user.clear(field);
  await user.type(field, "abc");
  await user.tab();

  expect(await screen.findByRole("alert")).toHaveTextContent("Anna summa muodossa 1,25.");
  expect(saves).toEqual([]);
  expect(await totalRow()).toHaveTextContent("450,00 €");
});

it("budget AC18: a negative amount shows the refusal and keeps the total", async () => {
  answerBudget();
  const user = userEvent.setup();
  render(<BudgetPage />);
  const field = await screen.findByRole("textbox", { name: "Auto" });

  await user.clear(field);
  await user.type(field, "-5");
  await user.tab();

  expect(await screen.findByRole("alert")).toHaveTextContent("Summa ei kelpaa.");
  expect(await totalRow()).toHaveTextContent("450,00 €");
});

it("budget AC18: a failed save shows an alert and keeps the total", async () => {
  answerBudget();
  server.use(
    http.put("/api/budget/:id", () =>
      HttpResponse.json(
        { error: "internal", message: "Tallennus ei onnistunut." },
        { status: 500 },
      ),
    ),
  );
  const user = userEvent.setup();
  render(<BudgetPage />);
  const field = await screen.findByRole("textbox", { name: "Auto" });

  await user.clear(field);
  await user.type(field, "150");
  await user.tab();

  expect(await screen.findByRole("alert")).toHaveTextContent("Tallennus ei onnistunut.");
  expect(await totalRow()).toHaveTextContent("450,00 €");
});

it("budget AC18: a failed load shows an alert", async () => {
  server.use(
    http.get("/api/budget", () =>
      HttpResponse.json({ error: "internal", message: "Lataus ei onnistunut." }, { status: 500 }),
    ),
  );
  render(<BudgetPage />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Lataus ei onnistunut.");
});
