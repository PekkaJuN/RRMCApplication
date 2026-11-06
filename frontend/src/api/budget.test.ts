import { expect, it } from "vitest";
import { answerBudget, answerComparison, BUDGET } from "../test/budget";
import { getBudget, getComparison, saveBudget } from "./budget";

it("budget AC1: reads the rows", async () => {
  answerBudget();

  expect(await getBudget()).toEqual({ ok: true, data: BUDGET });
});

it("budget AC2: saves with PUT and answers with the new total", async () => {
  const saves = answerBudget();

  const result = await saveBudget(7, 15000);

  expect(saves).toEqual([[7, 15000]]);
  expect(result.ok && result.data.total_cents).toBe(60000);
});

it("budget AC30: a calendar period sends only the month", async () => {
  const queries = answerComparison();

  await getComparison({ month: "2026-10", kind: "calendar" });

  expect(queries).toEqual(["month=2026-10"]);
});

it("budget AC30: a 15–14 period sends the kind", async () => {
  const queries = answerComparison();

  await getComparison({ month: "2026-10", kind: "mid" });

  expect(queries).toEqual(["month=2026-10&period=mid"]);
});
