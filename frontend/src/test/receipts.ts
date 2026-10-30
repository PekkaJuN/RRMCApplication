import type { CatalogItem } from "../api/catalog";
import type { CategorySource, Receipt, ReceiptLine, ReceiptSummary } from "../api/receipts";
import { defaultItems, itemNamed } from "./catalog";

/** The default catalog, whose ids the receipt fixtures use. */
export const ITEMS: CatalogItem[] = defaultItems();

export const DAIRY = itemNamed(ITEMS, "Maitotuotteet");
export const DRINKS = itemNamed(ITEMS, "Juomat");

/** A line in a category of the default catalog, or without a category. */
export function line(
  id: number,
  name: string,
  amount: number,
  category: CatalogItem | null,
  source: CategorySource | null,
  isDepositRefund = false,
): ReceiptLine {
  const group = category && ITEMS.find((item) => item.id === category.parent_id);
  return {
    id,
    position: id % 100,
    name,
    amount_cents: amount,
    is_deposit_refund: isDepositRefund,
    category_id: category?.id ?? null,
    category_name: category?.name ?? null,
    group_name: group?.name ?? null,
    category_source: source,
  };
}

function receipt(id: number, fields: Partial<Receipt>): Receipt {
  return {
    id,
    file_name: "kuitti.jpg",
    imported_at: "2026-10-28T10:00:01Z",
    store: "Testikauppa",
    purchase_date: "2026-10-05",
    total_cents: 349,
    reviewed: false,
    lines: [],
    line_sum_cents: 0,
    difference_cents: 349,
    warning: true,
    subtotals: [],
    ...fields,
  };
}

const DAIRY_SUBTOTAL = {
  category_id: DAIRY.id,
  category_name: "Maitotuotteet",
  group_name: "Ruoka",
};
const DRINKS_SUBTOTAL = { category_id: DRINKS.id, category_name: "Juomat", group_name: null };

/** Receipt A of the spec: Maito remembered, Limu suggested by the model. */
export const RECEIPT_A: Receipt = receipt(3, {
  lines: [line(101, "Maito", 125, DAIRY, "remembered"), line(102, "Limu", 224, DRINKS, "model")],
  line_sum_cents: 349,
  difference_cents: 0,
  warning: false,
  subtotals: [
    { ...DAIRY_SUBTOTAL, amount_cents: 125 },
    { ...DRINKS_SUBTOTAL, amount_cents: 224 },
  ],
});

/** Receipt A as the backend answers after Limu was set to Maitotuotteet (AC13, AC24). */
export const RECEIPT_A_LIMU_DAIRY: Receipt = {
  ...RECEIPT_A,
  lines: [line(101, "Maito", 125, DAIRY, "remembered"), line(102, "Limu", 224, DAIRY, "user")],
  subtotals: [{ ...DAIRY_SUBTOTAL, amount_cents: 349 }],
};

/** Receipt A with a line without category and a deposit refund (AC23). */
export const RECEIPT_A_MORE: Receipt = {
  ...RECEIPT_A,
  lines: [
    ...RECEIPT_A.lines,
    line(103, "Outo", 50, null, null),
    line(104, "Panttipalautus", -40, null, null, true),
  ],
};

/** The receipt of AC8 and AC25, with total 500. */
export const RECEIPT_AC8: Receipt = receipt(5, {
  total_cents: 500,
  lines: [
    line(501, "Maito", 125, DAIRY, "remembered"),
    line(502, "Limu", 224, DRINKS, "model"),
    line(503, "Jogurtti", 99, DAIRY, "remembered"),
    line(504, "Outo", 50, null, null),
    line(505, "Panttipalautus", -40, null, null, true),
  ],
  line_sum_cents: 458,
  difference_cents: 42,
  warning: true,
  subtotals: [
    { ...DAIRY_SUBTOTAL, amount_cents: 224 },
    { ...DRINKS_SUBTOTAL, amount_cents: 224 },
    { category_id: null, category_name: null, group_name: null, amount_cents: 50 },
  ],
});

/** A receipt imported before reading existed (AC7, AC26). */
export const RECEIPT_OLD: Receipt = receipt(6, {
  store: null,
  purchase_date: null,
  total_cents: null,
  difference_cents: null,
});

export const SUMMARY_A: ReceiptSummary = {
  id: 3,
  purchase_date: "2026-10-05",
  store: "Testikauppa",
  total_cents: 349,
  warning: false,
  reviewed: true,
};

export const SUMMARY_B: ReceiptSummary = {
  id: 4,
  purchase_date: "2026-10-06",
  store: "Kauppa B",
  total_cents: 500,
  warning: true,
  reviewed: false,
};
