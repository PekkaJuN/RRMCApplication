import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { getTotals, type Totals } from "../api/totals";
import { fi } from "../i18n/fi";
import { PAGE_PATHS } from "../navigation";
import {
  currentMonth,
  currentWeek,
  isUnitValue,
  periodFromSearch,
  periodToSearch,
  type Period,
  type PeriodUnit,
} from "../period";
import { TotalsTable } from "./TotalsTable";

function periodFromAddress(): Period {
  return periodFromSearch(window.location.search) ?? currentMonth(new Date());
}

function addressOf(period: Period): string {
  return `${PAGE_PATHS.totals}${periodToSearch(period)}`;
}

/** The Yhteenveto page: category totals per week and month of a chosen period (FR-22,
 * FR-25). The period lives in the address, so a reload and the back button keep it. */
export function TotalsPage() {
  const [period, setPeriod] = useState<Period>(periodFromAddress);
  // The inputs' text; it differs from `period` only while an input is emptied.
  const [draft, setDraft] = useState<Period>(period);
  const [totals, setTotals] = useState<Totals | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<ReadonlySet<number>>(new Set());
  // Only the answer to the latest request is shown, so fast changes cannot show old totals.
  const latestRequest = useRef(0);

  useEffect(() => {
    // The address always shows the period, also when it was opened without one.
    window.history.replaceState(null, "", addressOf(periodFromAddress()));
    const onPopState = () => {
      if (window.location.pathname === PAGE_PATHS.totals) {
        const next = periodFromAddress();
        setPeriod(next);
        setDraft(next);
      }
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    const request = ++latestRequest.current;
    void getTotals(period).then((result) => {
      if (request !== latestRequest.current) {
        return;
      }
      if (result.ok) {
        setTotals(result.data);
        setError(null);
      } else {
        setTotals(null);
        setError(result.error.message);
      }
    });
    return () => {
      // A request still running when the page closes is not shown either.
      latestRequest.current += 1;
    };
  }, [period]);

  function choose(next: Period) {
    setDraft(next);
    if (!isUnitValue(next.unit, next.from) || !isUnitValue(next.unit, next.to)) {
      return;
    }
    window.history.pushState(null, "", addressOf(next));
    setPeriod(next);
  }

  function changeUnit(event: ChangeEvent<HTMLSelectElement>) {
    const unit = event.target.value as PeriodUnit;
    choose(unit === "week" ? currentWeek(new Date()) : currentMonth(new Date()));
  }

  function toggle(groupId: number) {
    const next = new Set(expanded);
    if (!next.delete(groupId)) {
      next.add(groupId);
    }
    setExpanded(next);
  }

  const inputType = draft.unit === "week" ? "week" : "month";
  const hasRows = totals !== null && totals.rows.length > 0;

  return (
    <section aria-labelledby="totals-heading">
      <h2 id="totals-heading">{fi.totals.heading}</h2>
      <p>
        <label>
          {fi.totals.unit}{" "}
          <select value={draft.unit} onChange={changeUnit}>
            <option value="month">{fi.totals.month}</option>
            <option value="week">{fi.totals.week}</option>
          </select>
        </label>{" "}
        <label>
          {fi.totals.from}{" "}
          <input
            type={inputType}
            value={draft.from}
            onChange={(event) => choose({ ...draft, from: event.target.value })}
          />
        </label>{" "}
        <label>
          {fi.totals.to}{" "}
          <input
            type={inputType}
            value={draft.to}
            onChange={(event) => choose({ ...draft, to: event.target.value })}
          />
        </label>
      </p>
      {error && <p role="alert">{error}</p>}
      {totals !== null && totals.unreviewed_receipts > 0 && (
        <p role="status">{fi.totals.unreviewed(totals.unreviewed_receipts)}</p>
      )}
      {totals !== null && totals.undated_receipts > 0 && (
        <p role="status">{fi.totals.undated(totals.undated_receipts)}</p>
      )}
      {totals !== null && !hasRows && <p>{fi.totals.empty}</p>}
      {totals !== null && hasRows && (
        <>
          <TotalsTable
            label={fi.totals.weeks}
            unit="week"
            columns={totals.weeks}
            rows={totals.rows}
            totals={totals.week_totals}
            expanded={expanded}
            onToggle={toggle}
          />
          <TotalsTable
            label={fi.totals.months}
            unit="month"
            columns={totals.months}
            rows={totals.rows}
            totals={totals.month_totals}
            expanded={expanded}
            onToggle={toggle}
          />
        </>
      )}
    </section>
  );
}
