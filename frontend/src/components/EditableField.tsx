import { useId, useRef, useState, type KeyboardEvent } from "react";
import { dateToText, parseDateText } from "../format";
import { fi } from "../i18n/fi";
import { DateInput } from "./DateInput";

interface Props {
  label: string;
  /** The saved value; shown whenever the user has nothing typed. A date is `YYYY-MM-DD`. */
  value: string;
  type?: "text" | "date";
  /** A date that comes from the calendar only (date field PC6). */
  pickerOnly?: boolean;
  /** A visible `<label>` instead of `aria-label`. */
  showLabel?: boolean;
  /** The input's class, e.g. `amount` for a money field. */
  className?: string;
  /** Save the typed text, a date as `YYYY-MM-DD`; resolves to the error message, or null when
   * it was saved. */
  onSave: (text: string) => Promise<string | null>;
}

/**
 * An input that saves when it is left or on Enter, and only when its text changed; Esc puts
 * back the saved value (line-editing PC12, PC14). A refused save keeps the typed text, so the
 * user can fix it, and shows the message next to the field. A date is typed as `dd.mm.yyyy`
 * and is checked here, so text that is not a date is never sent (date field PC2, PC4).
 */
export function EditableField({
  label,
  value,
  type = "text",
  pickerOnly,
  showLabel,
  className,
  onSave,
}: Props) {
  const id = useId();
  // null: nothing typed, the saved value shows.
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The text whose save is waiting, so Enter and then leaving the field save it once.
  const saving = useRef<string | null>(null);
  const shown = type === "date" ? dateToText(value) : value;

  async function save(text = draft) {
    if (text === null || text === saving.current) {
      return;
    }
    if (text === shown) {
      setDraft(null);
      setError(null);
      return;
    }
    let sent = text;
    if (type === "date") {
      const date = parseDateText(text);
      if (date === null) {
        setError(fi.dateField.invalid);
        return;
      }
      if (date === value) {
        setDraft(null);
        setError(null);
        return;
      }
      sent = date;
    }
    saving.current = text;
    const message = await onSave(sent);
    saving.current = null;
    if (message === null) {
      // Text typed while the save waited is not saved yet, so it stays.
      setDraft((current) => (current === text ? null : current));
    }
    setError(message);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      void save();
    } else if (event.key === "Escape") {
      setDraft(null);
      setError(null);
    }
  }

  return (
    <>
      {showLabel && <label htmlFor={id}>{label}</label>}
      {type === "date" ? (
        <DateInput
          id={id}
          label={label}
          ariaLabel={showLabel ? undefined : label}
          pickerOnly={pickerOnly}
          text={draft ?? shown}
          onTextChange={(text) => {
            setDraft(text);
            setError(null);
          }}
          onPick={(text) => {
            setDraft(text);
            void save(text);
          }}
          onBlur={() => void save()}
          onKeyDown={onKeyDown}
        />
      ) : (
        <input
          id={id}
          type="text"
          className={className}
          aria-label={showLabel ? undefined : label}
          value={draft ?? shown}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={() => void save()}
          onKeyDown={onKeyDown}
        />
      )}
      {error && <span role="alert"> {error}</span>}
    </>
  );
}
