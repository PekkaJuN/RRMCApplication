import { useEffect, useRef, type KeyboardEvent } from "react";
import { dateToText, parseDateText } from "../format";
import { fi } from "../i18n/fi";

interface Props {
  id: string;
  /** The field's name in the calendar button's name. */
  label: string;
  text: string;
  /** The text field's own name, when no `<label>` points to `id`. */
  ariaLabel?: string;
  /** The day comes from the calendar only: the text cannot be edited (date field PC6). */
  pickerOnly?: boolean;
  onTextChange: (text: string) => void;
  /** A day picked from the calendar, as the field's text. */
  onPick: (text: string) => void;
  onBlur: () => void;
  onKeyDown?: (event: KeyboardEvent<HTMLInputElement>) => void;
}

/**
 * A date as `dd.mm.yyyy` text with a calendar button (date field PC1, PC3). A native date
 * input shows the format of the browser's language, so it stays only as the calendar.
 */
export function DateInput({
  id,
  label,
  text,
  ariaLabel,
  pickerOnly,
  onTextChange,
  onPick,
  onBlur,
  onKeyDown,
}: Props) {
  const picker = useRef<HTMLInputElement>(null);
  const pickerValue = parseDateText(text) ?? "";

  useEffect(() => {
    if (picker.current !== null) {
      picker.current.value = pickerValue;
    }
  }, [pickerValue]);

  // The native `change`, not React's `onChange`: that listens to `input`, which Chromium fires
  // on every step inside the open calendar, before anything is chosen (date field PC3).
  useEffect(() => {
    const element = picker.current;
    if (element === null) {
      return;
    }
    const pick = () => {
      if (element.value !== "") {
        onPick(dateToText(element.value));
      }
    };
    element.addEventListener("change", pick);
    return () => element.removeEventListener("change", pick);
  }, [onPick]);

  return (
    <span className="date-input">
      <input
        id={id}
        type="text"
        placeholder={fi.dateField.placeholder}
        aria-label={ariaLabel}
        readOnly={pickerOnly}
        value={text}
        onClick={pickerOnly ? () => picker.current?.showPicker() : undefined}
        onChange={(event) => onTextChange(event.target.value)}
        onBlur={onBlur}
        onKeyDown={onKeyDown}
      />
      <input ref={picker} className="date-picker" type="date" tabIndex={-1} aria-hidden="true" />
      <button
        type="button"
        aria-label={fi.dateField.calendar(label)}
        onClick={() => picker.current?.showPicker()}
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" width="16" height="16">
          <path
            fill="currentColor"
            d="M5 1v1H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V3a1 1 0 0 0-1-1h-2V1h-1v1H6V1H5zM3 6h10v7H3V6z"
          />
        </svg>
      </button>
    </span>
  );
}
