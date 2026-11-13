import { expect, it } from "vitest";
import { answerArchive, answerArchiveTotals, OVERVIEW, TOTALS } from "../test/archive";
import {
  archiveCsvUrl,
  archiveYear,
  deleteArchivedYear,
  getArchive,
  getArchiveTotals,
} from "./archive";

it("archiving AC17: reads the overview", async () => {
  answerArchive();

  expect(await getArchive()).toEqual({ ok: true, data: OVERVIEW });
});

it("archiving AC33: archives a year with POST", async () => {
  const requests = answerArchive();

  const result = await archiveYear(2025);

  expect(requests.archived).toEqual([2025]);
  expect(result.ok && result.data.receipts).toBe(12);
});

it("archiving AC37: a refusal keeps the backend's code and message", async () => {
  answerArchive({
    archiveError: {
      status: 409,
      body: { error: "unreviewed_receipts", message: "Ei voi.", count: 2 },
    },
  });

  expect(await archiveYear(2024)).toEqual({
    ok: false,
    error: { code: "unreviewed_receipts", message: "Ei voi." },
  });
});

it("archiving AC38: deletes a year with DELETE", async () => {
  const requests = answerArchive();

  const result = await deleteArchivedYear(2025);

  expect(requests.deleted).toEqual([2025]);
  expect(result.ok && result.data.lines).toBe(140);
});

it("archiving AC39: reads the year totals", async () => {
  answerArchiveTotals();

  expect(await getArchiveTotals(2025)).toEqual({ ok: true, data: TOTALS });
});

it("archiving AC41: a year not archived is not_found", async () => {
  answerArchiveTotals();

  const result = await getArchiveTotals(2023);

  expect(!result.ok && result.error.code).toBe("not_found");
});

it("archiving AC39: the CSV file's URL", () => {
  expect(archiveCsvUrl(2025)).toBe("/api/export/archive/2025");
});
