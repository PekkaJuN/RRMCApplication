import { useId, useState, type FormEvent } from "react";
import type { NewLine } from "../api/receipts";
import { parseCents } from "../format";
import { fi } from "../i18n/fi";

interface Props {
  /** Add the line; resolves to the error message, or null when it was added. */
  onAdd: (line: NewLine) => Promise<string | null>;
}

/** The `Uusi rivi` form under the line table (line-editing PC6, PC12). */
export function AddLineForm({ onAdd }: Props) {
  const headingId = useId();
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [isRefund, setIsRefund] = useState(false);
  const [amountError, setAmountError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const cents = parseCents(amount);
    if (cents === null) {
      setAmountError(fi.receipt.amountFormat);
      return;
    }
    setAmountError(null);
    const message = await onAdd({ name, amount_cents: cents, is_deposit_refund: isRefund });
    setError(message);
    if (message === null) {
      setName("");
      setAmount("");
      setIsRefund(false);
    }
  }

  return (
    <form aria-labelledby={headingId} onSubmit={(event) => void submit(event)}>
      <h3 id={headingId}>{fi.receipt.newLine}</h3>
      <label>
        {fi.receipt.product}{" "}
        <input value={name} onChange={(event) => setName(event.target.value)} />
      </label>{" "}
      <label>
        {fi.receipt.amount}{" "}
        <input value={amount} onChange={(event) => setAmount(event.target.value)} />
      </label>
      {amountError && <span role="alert"> {amountError}</span>}{" "}
      <label>
        <input
          type="checkbox"
          checked={isRefund}
          onChange={(event) => setIsRefund(event.target.checked)}
        />{" "}
        {fi.receipt.depositRefund}
      </label>{" "}
      <button type="submit">{fi.receipt.addLine}</button>
      {error && <span role="alert"> {error}</span>}
    </form>
  );
}
