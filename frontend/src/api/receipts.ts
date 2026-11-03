import { apiDelete, apiGet, apiPatch, apiPost, type ApiResult } from "./client";

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
  /** Null for a receipt typed in without an image (receipt-management PC6). */
  file_name: string | null;
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

/** The fields of a line edit; send at least one (line-editing PC1). */
export interface LineChanges {
  name?: string;
  amount_cents?: number;
  is_deposit_refund?: boolean;
  category_id?: number;
}

/** A line to add (line-editing PC6). */
export interface NewLine {
  name: string;
  amount_cents: number;
  is_deposit_refund: boolean;
}

/** The receipt fields of an edit; send at least one (line-editing PC8). */
export interface ReceiptChanges {
  store?: string;
  purchase_date?: string;
  total_cents?: number;
  reviewed?: boolean;
}

/** Every write answers with the whole receipt: an edit can move other lines of a product. */
export function editLine(
  receiptId: number,
  lineId: number,
  changes: LineChanges,
): Promise<ApiResult<Receipt>> {
  return apiPatch<Receipt>(`/api/receipts/${receiptId}/lines/${lineId}`, changes);
}

export function addLine(receiptId: number, line: NewLine): Promise<ApiResult<Receipt>> {
  return apiPost<Receipt>(`/api/receipts/${receiptId}/lines`, line);
}

export function deleteLine(receiptId: number, lineId: number): Promise<ApiResult<Receipt>> {
  return apiDelete<Receipt>(`/api/receipts/${receiptId}/lines/${lineId}`);
}

export function editReceipt(id: number, changes: ReceiptChanges): Promise<ApiResult<Receipt>> {
  return apiPatch<Receipt>(`/api/receipts/${id}`, changes);
}

export function setLineCategory(
  receiptId: number,
  lineId: number,
  categoryId: number,
): Promise<ApiResult<Receipt>> {
  return editLine(receiptId, lineId, { category_id: categoryId });
}

export function setReviewed(id: number, reviewed: boolean): Promise<ApiResult<Receipt>> {
  return editReceipt(id, { reviewed });
}

export function receiptImageUrl(id: number): string {
  return `/api/receipts/${id}/image`;
}

/** A receipt to type in; leave `image_file_name` out for no image (receipt-management PC3). */
export interface NewReceipt {
  store: string;
  purchase_date: string;
  total_cents: number;
  image_file_name?: string;
}

export function createReceipt(receipt: NewReceipt): Promise<ApiResult<Receipt>> {
  return apiPost<Receipt>("/api/receipts", receipt);
}

/** Deletes an unreviewed receipt and its lines (receipt-management PC1). */
export function deleteReceipt(id: number): Promise<ApiResult<undefined>> {
  return apiDelete(`/api/receipts/${id}`);
}

/** Mirrors GET /api/failed-images. */
export interface FailedImages {
  file_names: string[];
}

export function failedImages(): Promise<ApiResult<FailedImages>> {
  return apiGet<FailedImages>("/api/failed-images");
}

/** The name goes in the query string, which the backend never logs (receipt-management PC8). */
export function failedImageUrl(name: string): string {
  return `/api/failed-images/image?name=${encodeURIComponent(name)}`;
}
