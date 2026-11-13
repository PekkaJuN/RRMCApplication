import { render, screen } from "@testing-library/react";
import { HttpResponse } from "msw";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { answerComparison, OCTOBER_COMPARISON } from "../test/budget";
import { answerTotals, OCTOBER } from "../test/totals";
import { ComparisonPage } from "./ComparisonPage";
import { TotalsPage } from "./TotalsPage";

// Archiving spec PC10: a period that touches an archived year says so.

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"], now: new Date(2026, 10, 5, 12) });
});

afterEach(() => {
  vi.useRealTimers();
});

it("archiving AC22: Yhteenveto names one archived year", async () => {
  window.history.replaceState(null, "", "/yhteenveto");
  answerTotals(() => HttpResponse.json({ ...OCTOBER, archived_years: [2025] }));
  render(<TotalsPage />);

  expect(await screen.findByText("Arkistoitu vuosi 2025 ei ole mukana.")).toHaveAttribute(
    "role",
    "status",
  );
});

it("archiving AC23: Yhteenveto names several archived years", async () => {
  window.history.replaceState(null, "", "/yhteenveto");
  answerTotals(() => HttpResponse.json({ ...OCTOBER, archived_years: [2024, 2025] }));
  render(<TotalsPage />);

  expect(
    await screen.findByText("Arkistoidut vuodet 2024, 2025 eivät ole mukana."),
  ).toBeInTheDocument();
});

it("archiving AC22: no note without archived years", async () => {
  window.history.replaceState(null, "", "/yhteenveto");
  answerTotals();
  render(<TotalsPage />);

  await screen.findByRole("table", { name: "Viikot" });
  expect(screen.queryByText(/Arkistoi/)).not.toBeInTheDocument();
});

it("archiving AC24: Vertailu names the archived year", async () => {
  window.history.replaceState(null, "", "/vertailu");
  answerComparison({ ...OCTOBER_COMPARISON, archived_years: [2025] });
  render(<ComparisonPage />);

  expect(await screen.findByText("Arkistoitu vuosi 2025 ei ole mukana.")).toHaveAttribute(
    "role",
    "status",
  );
});
