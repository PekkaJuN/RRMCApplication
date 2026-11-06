import { useEffect, useId, useState, type FormEvent } from "react";
import { createReceipt, failedImages, failedImageUrl, type NewReceipt } from "../api/receipts";
import { dateToText, parseCents, parseDateText } from "../format";
import { fi } from "../i18n/fi";
import { DateInput } from "./DateInput";

interface Props {
  /** Called with the new receipt's id after it was created. */
  onCreated: (id: number) => void;
  onCancel: () => void;
}

/** The `Uusi kuitti` form on the Kuitit page (receipt-management PC11). */
export function NewReceiptForm({ onCreated, onCancel }: Props) {
  const headingId = useId();
  const dateId = useId();
  const [store, setStore] = useState("");
  const [date, setDate] = useState("");
  const [total, setTotal] = useState("");
  const [image, setImage] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const [listError, setListError] = useState<string | null>(null);
  const [previewFailed, setPreviewFailed] = useState(false);
  const [dateError, setDateError] = useState<string | null>(null);
  const [totalError, setTotalError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void failedImages().then((result) => {
      if (cancelled) {
        return;
      }
      if (result.ok) {
        setImages(result.data.file_names);
      } else {
        setListError(result.error.message);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  /** On leaving the field: an empty date is checked only when the form is sent. */
  function checkDate() {
    const parsed = parseDateText(date);
    if (parsed !== null) {
      setDate(dateToText(parsed));
    }
    setDateError(parsed === null && date !== "" ? fi.dateField.invalid : null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const cents = parseCents(total);
    // Read from the text at submit, so an old valid date cannot go with an invalid edit.
    const purchaseDate = parseDateText(date);
    setDateError(
      date === "" ? fi.newReceipt.dateMissing : purchaseDate ? null : fi.dateField.invalid,
    );
    setTotalError(cents === null ? fi.receipt.amountFormat : null);
    if (purchaseDate !== null) {
      setDate(dateToText(purchaseDate));
    }
    if (purchaseDate === null || cents === null) {
      return;
    }
    const receipt: NewReceipt = { store, purchase_date: purchaseDate, total_cents: cents };
    if (image !== "") {
      receipt.image_file_name = image;
    }
    setError(null);
    setIsSending(true);
    const result = await createReceipt(receipt);
    if (result.ok) {
      onCreated(result.data.id);
    } else {
      setIsSending(false);
      setError(result.error.message);
    }
  }

  return (
    <form
      className="new-receipt"
      aria-labelledby={headingId}
      onSubmit={(event) => void submit(event)}
    >
      <h3 id={headingId}>{fi.newReceipt.heading}</h3>
      <p>
        <label>
          {fi.receipt.store}{" "}
          <input value={store} onChange={(event) => setStore(event.target.value)} />
        </label>{" "}
        <label htmlFor={dateId}>{fi.receipt.date}</label>{" "}
        <DateInput
          id={dateId}
          label={fi.receipt.date}
          text={date}
          onTextChange={(text) => {
            setDate(text);
            setDateError(null);
          }}
          onPick={(text) => {
            setDate(text);
            setDateError(null);
          }}
          onBlur={checkDate}
        />
        {dateError && <span role="alert"> {dateError}</span>}{" "}
        <label>
          {fi.receipt.total}{" "}
          <input
            className="amount"
            value={total}
            onChange={(event) => setTotal(event.target.value)}
          />
        </label>
        {totalError && <span role="alert"> {totalError}</span>}
      </p>
      <p>
        <label>
          {fi.newReceipt.image}{" "}
          <select
            value={image}
            onChange={(event) => {
              setImage(event.target.value);
              setPreviewFailed(false);
            }}
          >
            <option value="">{fi.newReceipt.noImage}</option>
            {images.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        {listError && <span role="alert"> {listError}</span>}
      </p>
      {image !== "" &&
        (previewFailed ? (
          <p>{fi.newReceipt.previewFailed}</p>
        ) : (
          <img
            className="new-receipt-preview"
            src={failedImageUrl(image)}
            alt={fi.newReceipt.preview}
            onError={() => setPreviewFailed(true)}
          />
        ))}
      <p>
        {/* Disabled while sending: a manual receipt has no duplicate check (AC36). */}
        <button type="submit" disabled={isSending}>
          {fi.newReceipt.create}
        </button>{" "}
        <button type="button" onClick={onCancel}>
          {fi.actions.cancel}
        </button>
        {error && <span role="alert"> {error}</span>}
      </p>
    </form>
  );
}
