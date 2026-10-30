import { useEffect, useState } from "react";
import { listCategories, type CatalogItem } from "../api/catalog";
import type { ApiResult } from "../api/client";
import {
  getReceipt,
  receiptImageUrl,
  setLineCategory,
  setReviewed,
  type Receipt,
  type Subtotal,
} from "../api/receipts";
import { formatCents, formatDate } from "../format";
import { fi } from "../i18n/fi";
import { isPlainLeftClick, PAGE_PATHS } from "../navigation";
import { CategorySelect } from "./CategorySelect";

interface Props {
  id: number;
  onBack: () => void;
}

// The app has no stylesheet; this one layout rule puts the image beside the lines (FR-16)
// and wraps them on a narrow window.
const COLUMNS = {
  display: "flex",
  flexWrap: "wrap",
  gap: "1rem",
  alignItems: "flex-start",
} as const;
const IMAGE_COLUMN = { flex: "1 1 20rem", maxWidth: "40rem" } as const;
const LINES_COLUMN = { flex: "2 1 24rem" } as const;

/** One receipt: the image beside its lines, categories, sums and review state. */
export function ReceiptPage({ id, onBack }: Props) {
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [items, setItems] = useState<CatalogItem[] | null>(null);
  const [itemsError, setItemsError] = useState<string | null>(null);
  const [imageMissing, setImageMissing] = useState(false);
  // While a change waits for its answer every control is disabled, so answers cannot arrive
  // out of order.
  const [busy, setBusy] = useState(false);
  const [lineErrors, setLineErrors] = useState<Record<number, string>>({});
  const [reviewError, setReviewError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getReceipt(id).then((result) => {
      if (cancelled) {
        return;
      }
      if (result.ok) {
        setReceipt(result.data);
      } else if (result.error.code === "not_found") {
        setNotFound(true);
      } else {
        setLoadError(result.error.message);
      }
    });
    void listCategories().then((result) => {
      if (cancelled) {
        return;
      }
      if (result.ok) {
        setItems(result.data);
      } else {
        setItemsError(result.error.message);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [id]);

  /** Send one change; the answer is the whole receipt, so sums and moved lines update (FR-19). */
  async function change(
    request: Promise<ApiResult<Receipt>>,
    showError: (message: string | null) => void,
  ) {
    setBusy(true);
    showError(null);
    const result = await request;
    setBusy(false);
    if (result.ok) {
      setReceipt(result.data);
    } else {
      showError(result.error.message);
    }
  }

  function chooseCategory(lineId: number, categoryId: number | null) {
    if (categoryId === null) {
      return;
    }
    void change(setLineCategory(id, lineId, categoryId), (message) =>
      setLineErrors((errors) => {
        const next = { ...errors };
        delete next[lineId];
        return message === null ? next : { ...next, [lineId]: message };
      }),
    );
  }

  return (
    <section aria-labelledby="receipt-heading">
      <a
        href={PAGE_PATHS.receipts}
        onClick={(event) => {
          if (isPlainLeftClick(event)) {
            event.preventDefault();
            onBack();
          }
        }}
      >
        {fi.receipt.back}
      </a>
      <h2 id="receipt-heading">{fi.receipt.heading}</h2>
      {notFound && <p>{fi.receipt.notFound}</p>}
      {loadError && <p role="alert">{loadError}</p>}
      {itemsError && <p role="alert">{itemsError}</p>}
      {receipt && (
        <>
          <dl>
            <dt>{fi.receipt.store}</dt>
            <dd>{receipt.store || fi.receipts.missing}</dd>
            <dt>{fi.receipt.date}</dt>
            <dd>
              {receipt.purchase_date ? formatDate(receipt.purchase_date) : fi.receipts.missing}
            </dd>
            <dt>{fi.receipt.total}</dt>
            <dd>
              {receipt.total_cents === null
                ? fi.receipts.missing
                : formatCents(receipt.total_cents)}
            </dd>
          </dl>
          <p>
            {receipt.reviewed ? fi.receipts.reviewed : fi.receipts.unreviewed}{" "}
            <button
              type="button"
              disabled={busy}
              onClick={() => void change(setReviewed(id, !receipt.reviewed), setReviewError)}
            >
              {receipt.reviewed ? fi.receipt.cancelConfirmation : fi.receipt.confirm}
            </button>
            {reviewError && <span role="alert"> {reviewError}</span>}
          </p>
          <Warning receipt={receipt} />
          <div style={COLUMNS}>
            <div style={IMAGE_COLUMN}>
              {imageMissing ? (
                <p>{fi.receipt.imageMissing}</p>
              ) : (
                <a href={receiptImageUrl(receipt.id)} target="_blank" rel="noreferrer">
                  <img
                    src={receiptImageUrl(receipt.id)}
                    alt={fi.receipt.image}
                    style={{ maxWidth: "100%" }}
                    onError={() => setImageMissing(true)}
                  />
                </a>
              )}
            </div>
            <div style={LINES_COLUMN}>
              <Lines
                receipt={receipt}
                items={items}
                disabled={busy || items === null}
                errors={lineErrors}
                onChoose={chooseCategory}
              />
              <p>{`${fi.receipt.lineSum} ${formatCents(receipt.line_sum_cents)}`}</p>
              <Subtotals subtotals={receipt.subtotals} />
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function Warning({ receipt }: { receipt: Receipt }) {
  if (!receipt.warning) {
    return null;
  }
  const text =
    receipt.total_cents === null || receipt.difference_cents === null
      ? fi.receipt.totalMissing
      : fi.receipt.mismatch(
          formatCents(receipt.line_sum_cents),
          formatCents(receipt.total_cents),
          formatCents(receipt.difference_cents),
        );
  return <p role="status">{text}</p>;
}

interface LinesProps {
  receipt: Receipt;
  items: CatalogItem[] | null;
  disabled: boolean;
  errors: Record<number, string>;
  onChoose: (lineId: number, categoryId: number | null) => void;
}

function Lines({ receipt, items, disabled, errors, onChoose }: LinesProps) {
  if (receipt.lines.length === 0) {
    return <p>{fi.receipt.noLines}</p>;
  }
  return (
    <table aria-label={fi.receipt.lines}>
      <thead>
        <tr>
          <th>{fi.receipt.product}</th>
          <th>{fi.receipt.amount}</th>
          <th>{fi.receipt.category}</th>
        </tr>
      </thead>
      <tbody>
        {receipt.lines.map((line) => (
          <tr key={line.id}>
            <td>{line.name}</td>
            <td>{formatCents(line.amount_cents)}</td>
            <td>
              {line.is_deposit_refund ? (
                fi.receipt.depositRefund
              ) : (
                <>
                  <CategorySelect
                    label={fi.receipt.categoryOf(line.name)}
                    items={items ?? []}
                    value={line.category_id}
                    disabled={disabled}
                    onChange={(categoryId) => onChoose(line.id, categoryId)}
                  />
                  {line.category_source === "model" && <> {fi.receipt.suggestion}</>}
                  {errors[line.id] && <span role="alert"> {errors[line.id]}</span>}
                </>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Subtotals({ subtotals }: { subtotals: Subtotal[] }) {
  if (subtotals.length === 0) {
    return null;
  }
  return (
    <>
      <h3 id="subtotals-heading">{fi.receipt.subtotals}</h3>
      <ul aria-labelledby="subtotals-heading">
        {subtotals.map((subtotal) => (
          <li key={subtotal.category_id ?? "none"}>
            {`${subtotalName(subtotal)} ${formatCents(subtotal.amount_cents)}`}
          </li>
        ))}
      </ul>
    </>
  );
}

function subtotalName(subtotal: Subtotal): string {
  if (subtotal.category_name === null) {
    return fi.receipt.noCategory;
  }
  return subtotal.group_name
    ? `${subtotal.group_name} > ${subtotal.category_name}`
    : subtotal.category_name;
}
