import { http, HttpResponse } from "msw";
import { expect, it } from "vitest";
import {
  DAIRY,
  FAILED_IMAGES,
  RECEIPT_A,
  RECEIPT_A_LIMU_DAIRY,
  RECEIPT_MANUAL,
  recordWrites,
  SUMMARY_A,
  SUMMARY_B,
} from "../test/receipts";
import { server } from "../test/server";
import {
  addLine,
  createReceipt,
  deleteLine,
  deleteReceipt,
  editLine,
  editReceipt,
  failedImages,
  failedImageUrl,
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

// Line editing (P5).

it("line-editing AC25: edits a line with PATCH on the line", async () => {
  const calls = recordWrites();

  expect(await editLine(3, 102, { name: "Vesi", amount_cents: -40 })).toEqual({
    ok: true,
    data: RECEIPT_A,
  });
  expect(calls).toEqual([
    {
      method: "PATCH",
      path: "/api/receipts/3/lines/102",
      body: { name: "Vesi", amount_cents: -40 },
    },
  ]);
});

it("line-editing AC30: adds a line with POST on the lines", async () => {
  const calls = recordWrites();
  const line = { name: "Banaani", amount_cents: 99, is_deposit_refund: false };

  expect(await addLine(3, line)).toEqual({ ok: true, data: RECEIPT_A });
  expect(calls).toEqual([{ method: "POST", path: "/api/receipts/3/lines", body: line }]);
});

it("line-editing AC31: deletes a line and gets the receipt back", async () => {
  const calls = recordWrites();

  expect(await deleteLine(3, 102)).toEqual({ ok: true, data: RECEIPT_A });
  expect(calls).toEqual([{ method: "DELETE", path: "/api/receipts/3/lines/102", body: null }]);
});

it("line-editing AC29: edits the receipt fields with PATCH on the receipt", async () => {
  const calls = recordWrites();

  expect(await editReceipt(3, { total_cents: 400, purchase_date: "2026-10-06" })).toEqual({
    ok: true,
    data: RECEIPT_A,
  });
  expect(calls).toEqual([
    {
      method: "PATCH",
      path: "/api/receipts/3",
      body: { total_cents: 400, purchase_date: "2026-10-06" },
    },
  ]);
});

it("receipt-management AC7: creates a receipt with POST /api/receipts", async () => {
  let body: unknown;
  server.use(
    http.post("/api/receipts", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json(RECEIPT_MANUAL, { status: 201 });
    }),
  );
  const fields = { store: "Testikauppa", purchase_date: "2026-10-05", total_cents: 349 };

  expect(await createReceipt(fields)).toEqual({ ok: true, data: RECEIPT_MANUAL });
  expect(body).toEqual(fields);
});

it("receipt-management AC1: deletes a receipt with DELETE /api/receipts/{id}", async () => {
  let deleted = false;
  server.use(
    http.delete("/api/receipts/3", () => {
      deleted = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );

  expect(await deleteReceipt(3)).toEqual({ ok: true, data: undefined });
  expect(deleted).toBe(true);
});

it("receipt-management AC16: lists the failed images", async () => {
  server.use(
    http.get("/api/failed-images", () => HttpResponse.json({ file_names: FAILED_IMAGES })),
  );

  expect(await failedImages()).toEqual({ ok: true, data: { file_names: FAILED_IMAGES } });
});

it("receipt-management AC30: the preview address of a failed image", () => {
  expect(failedImageUrl("IMG_2.jpg")).toBe("/api/failed-images/image?name=IMG_2.jpg");
  expect(failedImageUrl("kuva #1.jpg")).toBe("/api/failed-images/image?name=kuva%20%231.jpg");
});
