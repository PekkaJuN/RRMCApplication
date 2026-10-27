import { useState } from "react";
import { fi } from "../i18n/fi";

interface Props {
  onConfirm: () => void;
}

/** A delete button that asks for confirmation in place; no browser dialog (AC28). */
export function ConfirmDelete({ onConfirm }: Props) {
  const [isAsking, setIsAsking] = useState(false);

  if (!isAsking) {
    return (
      <button type="button" onClick={() => setIsAsking(true)}>
        {fi.actions.delete}
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
