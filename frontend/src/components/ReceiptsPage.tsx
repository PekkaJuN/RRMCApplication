import { useEffect, useState } from "react";
import { listReceipts, type ReceiptSummary } from "../api/receipts";
import { formatCents, formatDate } from "../format";
import { fi } from "../i18n/fi";
import { isPlainLeftClick, receiptPath } from "../navigation";
import { NewReceiptForm } from "./NewReceiptForm";

interface Props {
  onOpen: (id: number) => void;
}

/** The Kuitit page: every receipt with its warning and review state (FR-21). */
export function ReceiptsPage({ onOpen }: Props) {
  const [receipts, setReceipts] = useState<ReceiptSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void listReceipts().then((result) => {
      if (cancelled) {
        return;
      }
      if (result.ok) {
        setReceipts(result.data);
      } else {
        setError(result.error.message);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section aria-labelledby="receipts-heading">
      <h2 id="receipts-heading">{fi.receipts.heading}</h2>
      {/* Closing the form unmounts it, so it opens empty again (receipt-management AC34). */}
      {isCreating ? (
        <NewReceiptForm onCreated={onOpen} onCancel={() => setIsCreating(false)} />
      ) : (
        <p>
          <button type="button" onClick={() => setIsCreating(true)}>
            {fi.newReceipt.open}
          </button>
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {receipts?.length === 0 && <p>{fi.receipts.empty}</p>}
      {receipts && receipts.length > 0 && (
        <div className="table-box">
          <table aria-label={fi.receipts.table}>
            <thead>
              <tr>
                <th>{fi.receipts.date}</th>
                <th>{fi.receipts.store}</th>
                <th className="amount">{fi.receipts.total}</th>
                <th>{fi.receipts.warning}</th>
                <th>{fi.receipts.state}</th>
              </tr>
            </thead>
            <tbody>
              {receipts.map((receipt) => (
                <tr key={receipt.id}>
                  <td>
                    <a
                      href={receiptPath(receipt.id)}
                      onClick={(event) => {
                        if (isPlainLeftClick(event)) {
                          event.preventDefault();
                          onOpen(receipt.id);
                        }
                      }}
                    >
                      {receipt.purchase_date
                        ? formatDate(receipt.purchase_date)
                        : fi.receipts.missing}
                    </a>
                  </td>
                  <td>{receipt.store || fi.receipts.missing}</td>
                  <td className="amount">
                    {receipt.total_cents === null
                      ? fi.receipts.missing
                      : formatCents(receipt.total_cents)}
                  </td>
                  <td>{receipt.warning ? fi.receipts.mismatch : ""}</td>
                  <td>{receipt.reviewed ? fi.receipts.reviewed : fi.receipts.unreviewed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
