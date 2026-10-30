import { http, HttpResponse } from "msw";
import { expect, it } from "vitest";
import { DAIRY, RECEIPT_A, RECEIPT_A_LIMU_DAIRY, SUMMARY_A, SUMMARY_B } from "../test/receipts";
import { server } from "../test/server";
import {
  getReceipt,
  listReceipts,
  receiptImageUrl,
  setLineCategory,
  setReviewed,
} from "./receipts";

it("AC20: lists the receipts with GET /api/receipts", async () => {
  server.use(http.get("/api/receipts", () => HttpResponse.json([SUMMARY_B, SUMMARY_A])));

  expect(await listReceipts()).toEqual({ ok: true, data: [SUMMARY_B, SUMMARY_A] });
});

it("AC22: reads one receipt with GET /api/receipts/{id}", async () => {
  server.use(http.get("/api/receipts/3", () => HttpResponse.json(RECEIPT_A)));

  expect(await getReceipt(3)).toEqual({ ok: true, data: RECEIPT_A });
});

it("AC24: sets a line's category with PATCH on the line", async () => {
  let body: unknown;
  server.use(
    http.patch("/api/receipts/3/lines/102", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json(RECEIPT_A_LIMU_DAIRY);
    }),
  );

  expect(await setLineCategory(3, 102, DAIRY.id)).toEqual({
    ok: true,
    data: RECEIPT_A_LIMU_DAIRY,
  });
  expect(body).toEqual({ category_id: DAIRY.id });
});

it("AC27: sets the review state with PATCH on the receipt", async () => {
  let body: unknown;
  server.use(
    http.patch("/api/receipts/3", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json({ ...RECEIPT_A, reviewed: true });
    }),
  );

  expect(await setReviewed(3, true)).toEqual({ ok: true, data: { ...RECEIPT_A, reviewed: true } });
  expect(body).toEqual({ reviewed: true });
});

it("AC28: an error answer keeps the code and message", async () => {
  server.use(
    http.patch("/api/receipts/3/lines/102", () =>
      HttpResponse.json(
        {
          error: "deposit_refund_line",
          message: "Pantinpalautusriville ei voi valita kategoriaa.",
        },
        { status: 422 },
      ),
    ),
  );

  expect(await setLineCategory(3, 102, DAIRY.id)).toEqual({
    ok: false,
    error: {
      code: "deposit_refund_line",
      message: "Pantinpalautusriville ei voi valita kategoriaa.",
    },
  });
});

it("AC22: the image address", () => {
  expect(receiptImageUrl(3)).toBe("/api/receipts/3/image");
});
