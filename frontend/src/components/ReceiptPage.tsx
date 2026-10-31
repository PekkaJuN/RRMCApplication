import { useEffect, useRef, useState } from "react";
import { listCategories, type CatalogItem } from "../api/catalog";
import type { ApiResult } from "../api/client";
import {
  addLine,
  deleteLine,
  editLine,
  editReceipt,
  getReceipt,
  receiptImageUrl,
  setLineCategory,
  setReviewed,
  type NewLine,
  type Receipt,
  type ReceiptLine,
  type Subtotal,
} from "../api/receipts";
import { formatCents, formatCentsInput, parseCents } from "../format";
import { fi } from "../i18n/fi";
import { isPlainLeftClick, PAGE_PATHS } from "../navigation";
import { AddLineForm } from "./AddLineForm";
import { CategorySelect } from "./CategorySelect";
import { ConfirmDelete } from "./ConfirmDelete";
import { EditableField } from "./EditableField";

interface Props {
  id: number;
  onBack: () => void;
}

/** Sends one change; resolves to the error message, or null when it was saved. */
type Send = (request: () => Promise<ApiResult<Receipt>>) => Promise<string | null>;

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

/** An amount field's save: text that is not an amount is refused without a request. */
function saveCents(text: string, save: (cents: number) => Promise<string | null>) {
  const cents = parseCents(text);
  return cents === null ? Promise.resolve(fi.receipt.amountFormat) : save(cents);
}

/** One receipt: the image beside its editable lines, categories, sums and review state. */
export function ReceiptPage({ id, onBack }: Props) {
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [items, setItems] = useState<CatalogItem[] | null>(null);
  const [itemsError, setItemsError] = useState<string | null>(null);
  const [imageMissing, setImageMissing] = useState(false);
  // Changes run one at a time, each after the previous answer, so answers cannot arrive out
  // of order; no control is disabled meanwhile, so the focus stays where the user is
  // (line-editing PC12).
  const queue = useRef<Promise<unknown>>(Promise.resolve());
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

  /** The answer is the whole receipt, so sums, marks and moved lines update (FR-19). */
  const send: Send = (request) => {
    const result = queue.current.then(async () => {
      const answer = await request();
      if (answer.ok) {
        setReceipt(answer.data);
        return null;
      }
      return answer.error.message;
    });
    queue.current = result;
    return result;
  };

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
          <p>
            <EditableField
              label={fi.receipt.store}
              showLabel
              value={receipt.store ?? ""}
              onSave={(text) => send(() => editReceipt(id, { store: text }))}
            />{" "}
            <EditableField
              label={fi.receipt.date}
              showLabel
              type="date"
              value={receipt.purchase_date ?? ""}
              onSave={(text) => send(() => editReceipt(id, { purchase_date: text }))}
            />{" "}
            <EditableField
              label={fi.receipt.total}
              showLabel
              value={receipt.total_cents === null ? "" : formatCentsInput(receipt.total_cents)}
              onSave={(text) =>
                saveCents(text, (cents) => send(() => editReceipt(id, { total_cents: cents })))
              }
            />
          </p>
          <p>
            {receipt.reviewed ? fi.receipts.reviewed : fi.receipts.unreviewed}{" "}
            <button
              type="button"
              onClick={() => {
                setReviewError(null);
                void send(() => setReviewed(id, !receipt.reviewed)).then(setReviewError);
              }}
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
              <Lines receipt={receipt} items={items} send={send} />
              <AddLineForm onAdd={(line: NewLine) => send(() => addLine(id, line))} />
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
  send: Send;
}

function Lines({ receipt, items, send }: LinesProps) {
  if (receipt.lines.length === 0) {
    return <p>{fi.receipt.noLines}</p>;
  }
  return (
    <table aria-label={fi.receipt.lines}>
      <thead>
        <tr>
          <th>{fi.receipt.product}</th>
          <th>{fi.receipt.amount}</th>
          <th>{fi.receipt.depositRefund}</th>
          <th>{fi.receipt.category}</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {receipt.lines.map((line) => (
          <LineRow key={line.id} receiptId={receipt.id} line={line} items={items} send={send} />
        ))}
      </tbody>
    </table>
  );
}

interface LineRowProps {
  receiptId: number;
  line: ReceiptLine;
  items: CatalogItem[] | null;
  send: Send;
}

/** One editable line. The refund checkbox, category and delete keep their own messages. */
function LineRow({ receiptId, line, items, send }: LineRowProps) {
  const [refundError, setRefundError] = useState<string | null>(null);
  const [categoryError, setCategoryError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  function sendWith(
    request: () => Promise<ApiResult<Receipt>>,
    showError: (message: string | null) => void,
  ) {
    showError(null);
    void send(request).then(showError);
  }

  return (
    <tr>
      <td>
        <EditableField
          label={fi.receipt.nameOf(line.name)}
          value={line.name}
          onSave={(text) => send(() => editLine(receiptId, line.id, { name: text }))}
        />
      </td>
      <td>
        <EditableField
          label={fi.receipt.amountOf(line.name)}
          value={formatCentsInput(line.amount_cents)}
          onSave={(text) =>
            saveCents(text, (cents) =>
              send(() => editLine(receiptId, line.id, { amount_cents: cents })),
            )
          }
        />
      </td>
      <td>
        {/* Checked from the saved line, so a refused change shows the saved state again. */}
        <input
          type="checkbox"
          aria-label={fi.receipt.refundOf(line.name)}
          checked={line.is_deposit_refund}
          onChange={(event) => {
            // Read now: React puts the controlled box back before the queued request runs.
            const isDepositRefund = event.target.checked;
            sendWith(
              () => editLine(receiptId, line.id, { is_deposit_refund: isDepositRefund }),
              setRefundError,
            );
          }}
        />
        {refundError && <span role="alert"> {refundError}</span>}
      </td>
      <td>
        {line.is_deposit_refund ? (
          fi.receipt.depositRefund
        ) : items === null ? (
          categoryText(line)
        ) : (
          <>
            <CategorySelect
              label={fi.receipt.categoryOf(line.name)}
              items={items}
              value={line.category_id}
              onChange={(categoryId) => {
                if (categoryId !== null) {
                  sendWith(() => setLineCategory(receiptId, line.id, categoryId), setCategoryError);
                }
              }}
            />
            {line.category_source === "model" && <> {fi.receipt.suggestion}</>}
            {categoryError && <span role="alert"> {categoryError}</span>}
          </>
        )}
      </td>
      <td>
        <ConfirmDelete
          onConfirm={() => sendWith(() => deleteLine(receiptId, line.id), setDeleteError)}
        />
        {deleteError && <span role="alert"> {deleteError}</span>}
      </td>
    </tr>
  );
}

/** A line's category while the categories load or after they failed (line-editing PC15). */
function categoryText(line: ReceiptLine): string {
  if (line.category_name === null) {
    return fi.receipts.missing;
  }
  return line.group_name ? `${line.group_name} > ${line.category_name}` : line.category_name;
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
