import { useEffect, useRef, useState } from "react";
import { getBudget, saveBudget, type Budget, type BudgetRow } from "../api/budget";
import type { ApiResult } from "../api/client";
import { formatCents, formatCentsInput, parseCents } from "../format";
import { fi } from "../i18n/fi";
import { EditableField } from "./EditableField";

/** The Budjetti page: one monthly budget per group and category without a group (FR-50). */
export function BudgetPage() {
  const [budget, setBudget] = useState<Budget | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Every answer holds all rows, so saves run one at a time: an older answer must not replace
  // a newer one (budget PC3). The API client never rejects, so one failure cannot stop the chain.
  const lastSave = useRef<Promise<ApiResult<Budget> | null>>(Promise.resolve(null));

  useEffect(() => {
    let isCurrent = true;
    void getBudget().then((result) => {
      if (!isCurrent) {
        return;
      }
      if (result.ok) {
        setBudget(result.data);
      } else {
        setError(result.error.message);
      }
    });
    return () => {
      isCurrent = false;
    };
  }, []);

  async function save(row: BudgetRow, text: string): Promise<string | null> {
    const cents = parseCents(text);
    if (cents === null) {
      return fi.receipt.amountFormat;
    }
    const saved = lastSave.current.then(() => saveBudget(row.id, cents));
    lastSave.current = saved;
    const result = await saved;
    if (!result.ok) {
      return result.error.message;
    }
    setBudget(result.data);
    return null;
  }

  return (
    <section aria-labelledby="budget-heading">
      <h2 id="budget-heading">{fi.budget.heading}</h2>
      {error && <p role="alert">{error}</p>}
      {budget !== null && (
        <div className="table-box">
          <table aria-label={fi.budget.heading}>
            <tbody>
              {budget.rows.map((row) => (
                <tr key={row.id}>
                  <th scope="row">{row.name}</th>
                  <td>
                    <EditableField
                      label={row.name}
                      value={formatCentsInput(row.amount_cents)}
                      className="amount"
                      onSave={(text) => save(row, text)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="row-total">
                <th scope="row">{fi.totals.total}</th>
                <td className="amount">{formatCents(budget.total_cents)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </section>
  );
}
