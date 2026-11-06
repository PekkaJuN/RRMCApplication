# Feature: Finnish date field

## Overview
- **Status:** Done
- **Created:** 2026-11-06
- **Updated:** 2026-11-06: Specify approved by the user; Plan added. Plan approved by the
  user; Tasks added; spec approved by the user; implementation started. The user checked the
  calendar on the receipt page. After the user's request, `Alkaen` and `Päättyen` of Yhteenveto
  are chosen from the calendar only (PC6, AC16, P2, P6). The review of that change found that
  moving inside the calendar counted as a pick: PC3 and AC17 added, P2 changed. Audited (PASS),
  see [Audit](#audit).
- **Depends on:** [Line editing](line-editing.md),
  [Receipt deletion and manual receipts](receipt-management.md)
- **Implements:** PRD FR-51 (new); NFR-15 for the date fields.
- **Affected subsystems:** [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
The date fields use the browser's native date input. The browser decides how it shows the date,
so the user sees `dd/mm/yyyy` although the app is Finnish. The app cannot change that format.
The user wants date fields in the form `dd.mm.yyyy`. The date is stored and sent as today.

## Current Behavior
- The receipt page's field `Päivä` is an `EditableField` with `type="date"`. It saves when it
  loses focus or on Enter, and Esc puts back the saved value
  ([line editing](line-editing.md)).
- The form `Uusi kuitti` has a native date input. An empty date gives
  `fi.newReceipt.dateMissing` ([receipt management](receipt-management.md)).
- The API takes `YYYY-MM-DD` and refuses other values with `422 invalid_date` and
  `Päivämäärä ei kelpaa.` ([API reference](../../docs/api-reference.md)).
- The planned `Aikaväli` of the Yhteenveto page used native date inputs
  ([date range spec](date-range-totals.md)).

## Proposed Change

### Concepts

- **Shown form:** `dd.mm.yyyy` with leading zeros, for example `05.10.2026`.
- **Accepted form:** one or two digits for the day and the month and four for the year, for
  example `5.10.2026` or `05.10.2026`. Only ASCII digits count. Surrounding spaces are ignored.
- A text is a **valid date** when it has the accepted form and is a real calendar day.
- A field **confirms** its text when it loses focus, on Enter, or when a day is picked from
  the calendar.

### Parts

- **PC1 Date field.** A text field with the placeholder `pp.kk.vvvv` and a calendar button next
  to it. It takes and gives a date as `YYYY-MM-DD`, so nothing changes outside the UI.
- **PC2 Confirming.** A confirmed valid date is shown in the shown form and given to the page.
  A confirmed text that is not valid is kept, gives the page nothing, and shows
  `Päivämäärä ei kelpaa.` with `role="alert"` next to the field. Editing the text clears
  the message.
- **PC3 Calendar.** The button opens the browser's calendar on the field's date, or on today
  when the field has no valid date. Picking a day fills the field and confirms it. Moving
  inside the calendar is not a pick, and Esc closes it without a change. The calendar's
  language and look come from the browser.
- **PC4 Receipt page.** `Päivä` uses the date field. It keeps the rules of `EditableField`: a
  confirmed date is saved once and only if it changed, Esc puts back the saved value, and a
  refused save keeps the text and shows the message. An empty `Päivä` of a receipt without a
  date can be left without an error. Emptying a saved date shows `Päivämäärä ei kelpaa.`,
  as the backend's answer does today, and sends no request.
- **PC5 New receipt form.** `Päivä` uses the date field. An empty date still gives
  `fi.newReceipt.dateMissing`. A text that is not valid gives `Päivämäärä ei kelpaa.`, and the
  form sends nothing.
- **PC6 Yhteenveto page.** `Alkaen` and `Päättyen` of `Aikaväli` use the date field
  ([date range spec](date-range-totals.md)) in a calendar-only form: the text cannot be edited,
  and a click on the field opens the calendar, as the button does. The other date fields can
  still be typed in.
- **PC7 Accessibility.** The text field has its visible label. The button is reachable by
  keyboard and has a name that includes the field's label.

### UI texts

| Place | Text |
|---|---|
| Placeholder of the field | `pp.kk.vvvv` |
| Name of the calendar button (`aria-label`) | `Avaa kalenteri: <label>` |
| Not a valid date | `Päivämäärä ei kelpaa.` (the existing backend text) |

### Out of Scope

- Stored and API dates. They stay `YYYY-MM-DD`.
- Dates shown as text, such as the receipt list's `5.10.2026`. They do not change.
- The month and week inputs of Yhteenveto and Vertailu. They hold no day, so they stay native.
- A calendar of our own, or a Finnish calendar in a browser that shows another language.
- A two-digit year.

## Acceptance Criteria

### AC1: Shows a date in the shown form
**Given** a field with the value `2026-10-05`
**When** it renders
**Then** the text field shows `05.10.2026`

### AC2: Accepted forms are confirmed
**Given** an empty date field
**When** the user types `05.10.2026`, then in a new field ` 5.10.2026 `, and confirms
**Then** both fields give `2026-10-05` and show `05.10.2026`

### AC3: Leap day
**Given** an empty date field
**When** the user confirms `29.02.2028`, and in a new field `29.02.2027`
**Then** the first gives `2028-02-29`; the second gives nothing and shows
`Päivämäärä ei kelpaa.`

### AC4: Invalid text
**Given** an empty date field
**When** the user confirms each of `30.02.2026`, `32.01.2026`, `01.13.2026`, `00.01.2026`,
`01.00.2026`, `1.1.26`, `2026-10-05`, `05/10/2026`, `abc` and a date with non-ASCII digits
**Then** each gives nothing, keeps the text, and shows `Päivämäärä ei kelpaa.` with
`role="alert"`

### AC5: Message clears
**Given** a field showing the message
**When** the user edits the text
**Then** the message is gone

### AC6: Calendar button
**Given** a field with the value `2026-10-05`
**When** the user activates `Avaa kalenteri: Päivä` by mouse or keyboard
**Then** the browser's calendar opens on 5.10.2026

### AC7: Picking a day
**Given** an open calendar
**When** the user picks 7.10.2026
**Then** the field shows `07.10.2026` and gives `2026-10-07` once

### AC8: Receipt page saves
**Given** a receipt dated `2026-10-05`
**When** the user types `06.10.2026` in `Päivä` and presses Enter, then leaves the field
**Then** one request sends `purchase_date` `2026-10-06`, and the field shows `06.10.2026`

### AC9: Receipt page ignores no change
**Given** a receipt dated `2026-10-05`
**When** the user types `5.10.2026` in `Päivä` and leaves the field
**Then** no request is sent and the field shows `05.10.2026`

### AC10: Receipt page Esc
**Given** the user has typed `06.10.2026` or an invalid text in `Päivä`
**When** the user presses Esc
**Then** the field shows the saved `05.10.2026`, no message shows, and no request is sent

### AC11: Receipt page invalid text
**Given** a receipt dated `2026-10-05`
**When** the user confirms `30.02.2026`, and in another try empties `Päivä` and leaves it
**Then** no request is sent and the message `Päivämäärä ei kelpaa.` shows

### AC12: Receipt without a date
**Given** a receipt without a purchase date
**When** the user moves through `Päivä` without typing
**Then** the field stays empty, no message shows, and no request is sent

### AC13: Refused save
**Given** the backend refuses a save with `Päivämäärä ei kelpaa.`
**When** the user confirms a valid date
**Then** the text stays and the message shows

### AC14: New receipt
**Given** the form `Uusi kuitti` with its other fields filled
**When** the user sends it with `Päivä` `15.09.2026`, then in another try empty, then in another
try `31.09.2026`
**Then** the first sends `purchase_date` `2026-09-15`; the second shows the existing date
missing message; the third shows `Päivämäärä ei kelpaa.`; the last two send nothing and keep
every value

### AC15: Accessibility
**Given** the receipt page, the form `Uusi kuitti` and the Yhteenveto page with `Aikaväli`
**When** the accessibility check of the style tests runs
**Then** it finds no violations, each text field is found by its label, and the calendar button
by its name

### AC16: Calendar-only field
**Given** a date field in the calendar-only form with the value `2026-10-05`
**When** the user types in it, and when the user clicks it
**Then** the text stays `05.10.2026`, and the click opens the calendar on 5.10.2026

### AC17: Moving inside the calendar is not a pick
**Given** an open calendar on 5.10.2026
**When** the user moves to other days and months with the arrow keys or the month buttons,
and then presses Esc
**Then** the field keeps `05.10.2026`, and the page saves or loads nothing

## Files to Modify

| File | Change |
|---|---|
| `frontend/src/components/DateInput.tsx` (new) | The text field, the picker and the button |
| `frontend/src/components/EditableField.tsx` | The date mode |
| `frontend/src/components/NewReceiptForm.tsx` | The date field |
| `frontend/src/format.ts` | Date text to and from `YYYY-MM-DD` |
| `frontend/src/i18n/fi.ts`, `frontend/src/styles.css` | The new texts and styles |
| Test files in [P8](#p8-tests) | New tests; existing tests after the specs below are corrected |
| `specs/PRD.md` | FR-51 (new) and the Next release |
| `specs/features/line-editing.md`, `specs/features/receipt-management.md`, `specs/features/receipt-review.md` | The date field's form in their ACs and notes |
| `specs/features/date-range-totals.md`, `specs/README.md` | The date range uses this field; status |
| `docs/subsystems/ui/README.md`, `docs/glossary.md`, `docs/content-plan.md` | The date field |

## Risk

- **What could break:** a wrong day when converting between the two forms; a date saved twice
  (Enter, then leaving) or on a calendar pick; browsers without the calendar's API; a hidden
  control that breaks keyboard use or the accessibility check. Existing E2E tests type
  `YYYY-MM-DD` into `Päivä` and change with the specs.
- **Rollback:** revert the commits. There is no migration and no data change.
- **Dependencies:** none new expected.

## Testing Strategy (MANDATORY)

### Unit tests

| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | Date to text | happy path | `2026-10-05` | call | `05.10.2026` | none |
| AC2 | Text to date | accepted forms | `05.10.2026`, ` 5.10.2026 ` | call | `2026-10-05` | none |
| AC3 | Text to date | leap day | `29.02.2028`, `29.02.2027` | call | `2028-02-29`; nothing | none |
| AC4 | Text to date | each invalid text | Each text of AC4 | call | Nothing | none |

### Integration tests

No backend change, so none apply. Component tests with MSW cover the pages:

| AC | Scenario | Steps | Expected outcome |
|---|---|---|---|
| AC1–AC5 | Field | Render, type, confirm | Texts, given dates and messages of the ACs |
| AC6 | Button | Click; press Enter on it | The calendar is asked to open |
| AC16 | Calendar-only | Type; click the field | The text stays; the calendar is asked to open |
| AC17 | Moving in the calendar | Fire `input` without `change` on the calendar input | Nothing is given |
| AC7 | Pick | Change the calendar's value | One given date; the text of AC7 |
| AC8–AC13 | Receipt page | Type, Enter, leave, Esc | Requests and messages of the ACs |
| AC14 | New receipt | Send the three tries | Request and messages of AC14 |

### E2E tests

| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC8, AC14 | Type a receipt's date | Create a receipt with `15.09.2026`, change the date on its page, reload | The field shows the new date in the shown form |
| AC15 | Accessibility | Open the three views | No violations |
| AC6, AC7, AC16, AC17 | Real calendar | Open it from the button and the field, move with the keyboard, press Esc, then pick a day | Nothing changes until the pick; the pick loads once |

The tests reach the browser's calendar window by keyboard only, so the user checks the mouse
during the audit.

### Coverage target

- Frontend: 80 % lines for the changed code; date conversion: every branch tested.

### Test data

- Synthetic fixtures only (no real receipts), as in the existing receipt tests.
- Mocks: MSW for the frontend; the calendar's open call in component tests.

## Related Documentation (MANDATORY)

- Tier 1: [API reference](../../docs/api-reference.md), [Glossary](../../docs/glossary.md)
- Tier 2: [ui](../../docs/subsystems/ui/README.md)
- ADRs: none
- Specs: [Line editing](line-editing.md), [Receipt deletion and manual
  receipts](receipt-management.md), [Free date range for totals](date-range-totals.md)


## Plan

### P0 Overview

```
format.ts       dateToText(iso), parseDateText(text)     pure conversion
DateInput.tsx   text input, hidden native picker, calendar button; holds no state
  ├─ EditableField (type="date")  draft, save, Esc, error   → ReceiptPage, TotalsPage
  └─ NewReceiptForm               its own text state, checked on leaving and on submit
```

Frontend only. No migration, no new dependency, no API change and no ADR. The native date input
stays only as the calendar: it is hidden and is not the field the user reads.

### P1 Conversion (`frontend/src/format.ts`)

- `dateToText(date: string): string`: `2026-10-05` → `05.10.2026`, `""` → `""`. It reorders the
  parts and does not check them, so `2026-02-30` from an address shows as `30.02.2026`, and the
  backend refuses it (date range AC19).
- `parseDateText(text: string): string | null`: trims, then
  `/^([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})$/`, which refuses other digits (AC4).
- The real-day check builds the day with `setUTCFullYear(year, month - 1, day)` and compares the
  month and the day it got back. `Date.UTC` is not used, because it maps the years 0–99 to the
  1900s. Year `0000` is refused, because the backend refuses it too.
- `formatDate` and `formatDayMonth` do not change (out of scope).

### P2 `DateInput` (`frontend/src/components/DateInput.tsx`, new)

```ts
interface Props {
  id: string;
  /** The button's name: `Avaa kalenteri: <label>`. */
  label: string;
  text: string;
  /** The field's own name when no `<label>` points to `id`. */
  ariaLabel?: string;
  onTextChange: (text: string) => void;
  /** A day picked from the calendar, as shown text. */
  onPick: (text: string) => void;
  onBlur: () => void;
  onKeyDown?: (event: KeyboardEvent<HTMLInputElement>) => void;
}
```

- It renders `<input type="text">` with the placeholder, the picker and the button.
- A prop `pickerOnly` makes the text input `readOnly` and opens the calendar on its click, which
  is a user action too. `EditableField` passes the prop on (PC6, AC16).
- The picker is `<input type="date" tabIndex={-1} aria-hidden="true">` with the class
  `date-picker`, and its value is `parseDateText(text) ?? ""`. An empty value opens the calendar
  on today (PC3, AC6).
- `date-picker` hides it visually with zero opacity and places it at the button, so the calendar
  opens there. It does not use `display: none`, because
  [MDN](https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/showPicker) does not
  say that `showPicker` works on such an element.
- The button is `type="button"` with `aria-label` `Avaa kalenteri: <label>` and an inline SVG
  icon marked `aria-hidden`. Its click calls `picker.current?.showPicker()`, which meets the
  user-activation rule. The method has been widely available since September 2022, so there is
  no fallback.
- The picker's native `change` event calls `onPick(dateToText(value))` through a listener on the
  element, and an empty value is ignored. React's `onChange` is not used: it listens to the
  `input` event, which Chromium fires on every step inside the open calendar. The picker is
  uncontrolled and an effect sets its value from `text`, so a step that is cancelled leaves no
  state behind (PC3, AC17).
- Styles go in `styles.css`: the text field fits `00.00.0000`, and the button keeps the existing
  button style.

### P3 `EditableField` (PC2, PC4, PC6)

With `type="date"`, the prop `value` stays `YYYY-MM-DD` and `onSave` gets `YYYY-MM-DD`.

- `shown` is `dateToText(value)` for a date and `value` otherwise. The input shows
  `draft ?? shown`.
- `save(text = draft)` takes the text, so a pick can save a text that is not yet in state:

```ts
if (text === null || text === saving.current) return;
if (text === shown) { setDraft(null); return; }
let sent = text;
if (type === "date") {
  const date = parseDateText(text);
  if (date === null) { setError(fi.dateField.invalid); return; } // AC11, AC4
  if (date === value) { setDraft(null); setError(null); return; } // AC9
  sent = date;
}
saving.current = text;
const message = await onSave(sent);
```

- `saving` holds the typed text, so Enter and then leaving save once (AC8). The rest of `save` is
  as today, with `text` in place of `sent` for the comparison with the draft.
- `text === shown` handles AC12: a receipt without a date gives `"" === ""`. Emptying a saved date
  gives `parseDateText("")` `null`, so the message shows and no request is sent (AC11).
- For a date the input's `onChange` also clears `error` (AC5). The text field keeps today's
  behavior.
- Esc already clears the draft and the error (AC10). A refused save keeps the draft (AC13).
- `onPick` runs `setDraft(text)` and `void save(text)`.
- The `<label htmlFor={id}>` names the text input, and `aria-label` is used without `showLabel`.
  The picker has no label, so `getByLabelText("Päivä")` finds the text field only.

### P4 `NewReceiptForm` (PC5)

- `date` holds the shown text, not `YYYY-MM-DD`.
- The `<label>` no longer wraps the input, because a wrapping label would also hold the button.
  It uses `htmlFor` with `useId`.
- `onBlur`: a non-empty text that is not valid sets `fi.dateField.invalid`; a valid text is
  rewritten as `dateToText(parsed)`; an empty text clears the error. The picker's `onPick` sets
  the text and clears the error, and `onTextChange` clears the error (AC5).
- `submit`: `date === ""` gives `dateMissing`; `parseDateText(date) === null` gives
  `fi.dateField.invalid`; otherwise the request sends the parsed value (AC14). A form cannot use
  the draft of `EditableField`, because an old valid date could be sent after an invalid edit.

### P5 Texts (`frontend/src/i18n/fi.ts`)

```ts
dateField: {
  placeholder: "pp.kk.vvvv",
  calendar: (label: string) => `Avaa kalenteri: ${label}`,
  invalid: "Päivämäärä ei kelpaa.",
},
```

The text repeats the backend's `INVALID_DATE`, because the field shows it without a request. The
backend's copy is kept for its own answers.

### P6 Yhteenveto

`Aikaväli` renders `EditableField` with `type="date"`, `pickerOnly`, `showLabel` and
`value={draft.from}` or
`draft.to`. `onSave` calls `choose` and resolves to `null`. The date range spec's P4 records this.
`EditableField` already follows a new `value` when no draft is held, so the back button works
(date range AC17).

### P7 Correcting the existing specs first

These are corrected before their tests change (AGENTS.md: the spec decides):

| Spec | Correction |
|---|---|
| `specs/PRD.md` | New row FR-51 in section 6.4 and in the Next release: "*Next release:* date fields show and accept `dd.mm.yyyy` and have a calendar button. Dates are stored and sent as `YYYY-MM-DD`." |
| `specs/features/line-editing.md` | `Päivä` shows `05.10.2026`, in the ACs that give its input value; the date stays `YYYY-MM-DD` in requests |
| `specs/features/receipt-management.md` | The ACs and the note on the date input: the field is the [date field](date-field.md), not `type="date"` |
| `specs/features/receipt-review.md` | AC22: the receipt page shows `05.10.2026`. The receipt list keeps `5.10.2026` |

Those specs stay Done. Each gets an `Updated` line that links this spec.

### P8 Tests

| Test file | ACs | Change |
|---|---|---|
| `frontend/src/format.test.ts` | AC1–AC4 | New |
| `frontend/src/components/DateInput.test.tsx` (new) | AC6, AC7, AC16, AC17, PC7 | `showPicker` is stubbed, because jsdom lacks it |
| `frontend/src/components/EditableField.test.tsx` | AC2–AC5, AC8–AC13 | New; the existing date test at the corrected spec |
| `frontend/src/components/ReceiptPage.test.tsx`, `frontend/src/App.test.tsx` | AC1, AC8 | Expected `Päivä` text at the corrected spec |
| `frontend/src/components/NewReceiptForm.test.tsx` | AC14 | New; existing date input at the corrected spec |
| `frontend/e2e/receipts.spec.ts`, `frontend/e2e/budget.spec.ts` | AC8, AC14 | Type the shown form; new journey |
| `frontend/e2e/style.spec.ts` | AC15 | The accessibility check covers the three views, and `showPicker` runs in a real browser without an error |

The real calendar window is checked by the user during the audit (see E2E tests above).

### P9 Plan checked against the ACs

| ACs | Covered by |
|---|---|
| AC1–AC5 | P1, P3, P4 |
| AC6, AC7 | P2, P3 `onPick`, P4 `onPick` |
| AC16 | P2, P6 |
| AC17 | P2 |
| AC8–AC13 | P3 |
| AC14 | P4 |
| AC15 | P2, P3, P4, P8 |

### P10 Documentation

- `docs/subsystems/ui/README.md`: `DateInput`, the date mode of `EditableField`, and the rule that
  date fields show `dd.mm.yyyy`.
- `docs/glossary.md`: `Date field`.
- `docs/api-reference.md` does not change: the API does not.

## Tasks

This spec comes before the [date range spec](date-range-totals.md). PC6 and the Yhteenveto part of
AC15 are done in that spec's T6 and T7, so the audit of this spec runs after them.

- [x] **T1 Correct the existing specs (P7).** Add FR-51 to `specs/PRD.md`, and correct
  `specs/features/line-editing.md`, `specs/features/receipt-management.md` and
  `specs/features/receipt-review.md`. No test: the
  later tasks follow the corrected text.
- [x] **T2 Conversion (P1).** AC1–AC4. `dateToText` and `parseDateText`. Test:
  `frontend/src/format.test.ts`.
- [x] **T3 `DateInput` and texts (P2, P5).** AC6, AC7, AC16, AC17, PC7. The component, `fi.dateField` and the
  styles. Test: `frontend/src/components/DateInput.test.tsx`.
- [x] **T4 Date mode of `EditableField` (P3).** AC2–AC5, AC8–AC13. Test:
  `frontend/src/components/EditableField.test.tsx`.
- [x] **T5 Receipt page (P3).** AC1, AC8. The page already passes `type="date"`, so its tests
  follow the corrected spec. Tests: `frontend/src/components/ReceiptPage.test.tsx`,
  `frontend/src/App.test.tsx`.
- [x] **T6 New receipt form (P4).** AC14. Test: `frontend/src/components/NewReceiptForm.test.tsx`.
- [x] **T7 E2E (P8).** AC8, AC14. A new journey, and the existing journeys type the shown form.
  Tests: `frontend/e2e/receipts.spec.ts`, `frontend/e2e/budget.spec.ts`.
- [x] **T8 Accessibility and the calendar call (P8).** AC15 for the receipt page and the form;
  AC6 in a real browser without an error. Test: `frontend/e2e/style.spec.ts`.
- [x] **T9 Documentation (P10).** `docs/subsystems/ui/README.md`, `docs/glossary.md`. Verify with
  the frontend tests, lint, format check and type check, and the E2E tests.

## Audit

Audited 2026-11-06 against this spec, with two independent reviews and a documentation
scan: **PASS**. The user tried the final build with the mouse.

- Acceptance criteria 17/17 and PC1–PC7 met. Coverage: frontend 98.8 % lines (target 80 %),
  `format.ts` 100 %, `DateInput.tsx` 94 %.
- Tests: backend 1320 passed, frontend 328 passed, E2E 36 passed (two runs, also the real
  calendar by keyboard); ruff, pyright, ESLint and tsc clean; container tests and `pip-audit`
  passed. The repository-wide `format:check` reports the known CRLF working-tree warning; the
  changed files pass Prettier with `--end-of-line auto`.
- The second review found that every step inside the open calendar counted as a pick, which
  saved a receipt's date or loaded totals. Fixed test first with the native `change` event
  (date field PC3, AC17; [learnings](../../docs/learnings.md)). The fix had no code review of its
  own; the tests and the user's mouse check cover it.
- The scan found one gap of this change and older count and order errors in the content plan;
  all are fixed. It did not check every identifier or the Tier 1 docs line by line.
- Security: no findings. No receipt data in tests or logs; the query string and the file names
  hold dates only. `npm audit`: 7 moderate findings; this change adds no dependency.
- Manual check: after the fix, the user confirmed with the mouse that browsing the calendar
  changes nothing and that picking a day works, on the receipt page and in `Aikaväli` (AC6,
  AC7, AC16, AC17). Tests reach the browser's calendar window by keyboard only. Firefox,
  Safari and real screen readers are not checked.
- Fixed during the audit (test first): picking the saved day left a false message; Enter in the
  new receipt form did not show the date with leading zeros; tests added for leaving a field
  while its save waits and for a refused pick.
- Later: a save refused on Enter is sent again when the field is left. The old `EditableField`
  did the same, and the data does not change.
