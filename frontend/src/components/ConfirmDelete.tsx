import { useState } from "react";
import { fi } from "../i18n/fi";

interface Props {
  /** The first button's text; `Poista` by default. */
  label?: string;
  /** True while the delete runs, so a second one cannot be started (receipt-management AC37). */
  disabled?: boolean;
  onConfirm: () => void;
}

/** A delete button that asks for confirmation in place; no browser dialog (AC28). */
export function ConfirmDelete({ label = fi.actions.delete, disabled = false, onConfirm }: Props) {
  const [isAsking, setIsAsking] = useState(false);

  if (!isAsking) {
    return (
      <button type="button" disabled={disabled} onClick={() => setIsAsking(true)}>
        {label}
      </button>
    );
  }
  return (
    <span>
      {fi.actions.confirmDelete}{" "}
      <button
        type="button"
        onClick={() => {
          setIsAsking(false);
          onConfirm();
        }}
      >
        {fi.actions.delete}
      </button>{" "}
      <button type="button" onClick={() => setIsAsking(false)}>
        {fi.actions.cancel}
      </button>
    </span>
  );
}
