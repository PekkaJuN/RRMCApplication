import { apiGet, apiPatch, type ApiResult } from "./client";

export type CategorySource = "remembered" | "model" | "user";

/** Mirrors the backend schema of a receipt in GET /api/receipts. */
export interface ReceiptSummary {
  id: number;
  purchase_date: string | null;
  store: string | null;
  total_cents: number | null;
  warning: boolean;
  reviewed: boolean;
}

/** Mirrors the backend schema of a receipt line; the category fields are null without one. */
export interface ReceiptLine {
  id: number;
  position: number;
  name: string;
  amount_cents: number;
  is_deposit_refund: boolean;
  category_id: number | null;
  category_name: string | null;
  group_name: string | null;
  category_source: CategorySource | null;
}

/** A category subtotal; `category_id` null is the lines without a category. */
export interface Subtotal {
  category_id: number | null;
  category_name: string | null;
  group_name: string | null;
  amount_cents: number;
}

/** Mirrors the backend schema of GET /api/receipts/{id}. The backend computes the sums. */
export interface Receipt {
  id: number;
  file_name: string;
  imported_at: string;
  store: string | null;
  purchase_date: string | null;
  total_cents: number | null;
  reviewed: boolean;
  lines: ReceiptLine[];
  line_sum_cents: number;
  difference_cents: number | null;
  warning: boolean;
  subtotals: Subtotal[];
}

export function listReceipts(): Promise<ApiResult<ReceiptSummary[]>> {
  return apiGet<ReceiptSummary[]>("/api/receipts");
}

export function getReceipt(id: number): Promise<ApiResult<Receipt>> {
  return apiGet<Receipt>(`/api/receipts/${id}`);
}

/** The answer is the whole receipt: the choice can move other lines of the same product. */
export function setLineCategory(
  receiptId: number,
  lineId: number,
  categoryId: number,
): Promise<ApiResult<Receipt>> {
  return apiPatch<Receipt>(`/api/receipts/${receiptId}/lines/${lineId}`, {
    category_id: categoryId,
  });
}

export function setReviewed(id: number, reviewed: boolean): Promise<ApiResult<Receipt>> {
  return apiPatch<Receipt>(`/api/receipts/${id}`, { reviewed });
}

export function receiptImageUrl(id: number): string {
  return `/api/receipts/${id}/image`;
}
