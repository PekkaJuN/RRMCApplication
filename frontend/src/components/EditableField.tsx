import { useId, useRef, useState } from "react";

interface Props {
  label: string;
  /** The saved value; shown whenever the user has nothing typed. */
  value: string;
  type?: "text" | "date";
  /** A visible `<label>` instead of `aria-label`. */
  showLabel?: boolean;
  /** Save the typed text; resolves to the error message, or null when it was saved. */
  onSave: (text: string) => Promise<string | null>;
}

/**
 * An input that saves when it is left or on Enter, and only when its text changed; Esc puts
 * back the saved value (line-editing PC12, PC14). A refused save keeps the typed text, so the
 * user can fix it, and shows the message next to the field.
 */
export function EditableField({ label, value, type = "text", showLabel, onSave }: Props) {
  const id = useId();
  // null: nothing typed, the saved value shows.
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The text whose save is waiting, so Enter and then leaving the field save it once.
  const saving = useRef<string | null>(null);

  async function save() {
    if (draft === null || draft === saving.current) {
      return;
    }
    if (draft === value) {
      setDraft(null);
      return;
    }
    const sent = draft;
    saving.current = sent;
    const message = await onSave(sent);
    saving.current = null;
    if (message === null) {
      // Text typed while the save waited is not saved yet, so it stays.
      setDraft((current) => (current === sent ? null : current));
    }
    setError(message);
  }

  return (
    <>
      {showLabel && <label htmlFor={id}>{label}</label>}
      <input
        id={id}
        type={type}
        aria-label={showLabel ? undefined : label}
        value={draft ?? value}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => void save()}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            void save();
          } else if (event.key === "Escape") {
            setDraft(null);
            setError(null);
          }
        }}
      />
      {error && <span role="alert"> {error}</span>}
    </>
  );
}
