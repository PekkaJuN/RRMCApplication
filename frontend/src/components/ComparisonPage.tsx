import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { getComparison, type Comparison } from "../api/budget";
import { comparisonPdfUrl } from "../api/export";
import {
  comparisonFromSearch,
  comparisonToSearch,
  currentComparison,
  type ComparisonKind,
  type ComparisonPeriod,
} from "../comparison";
import { formatDate } from "../format";
import { fi } from "../i18n/fi";
import { PAGE_PATHS } from "../navigation";
import { isUnitValue } from "../period";
import { ComparisonMonthTable, ComparisonWeekTable } from "./ComparisonTable";

function periodFromAddress(): ComparisonPeriod {
  return comparisonFromSearch(window.location.search, new Date());
}

function addressOf(period: ComparisonPeriod): string {
  return `${PAGE_PATHS.comparison}${comparisonToSearch(period)}`;
}

/** The Vertailu page: the budget against reviewed spending of one period (FR-50). The period
 * lives in the address, so a reload and the back button keep it. */
export function ComparisonPage() {
  const [period, setPeriod] = useState<ComparisonPeriod>(periodFromAddress);
  // The input's text; it differs from `period.month` only while the input is emptied.
  const [monthDraft, setMonthDraft] = useState(period.month);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isWeeksOpen, setIsWeeksOpen] = useState(false);
  // Only the answer to the latest request is shown, so fast changes cannot show old figures.
  const latestRequest = useRef(0);

  useEffect(() => {
    // The address always shows the period, also when it was opened without one.
    window.history.replaceState(null, "", addressOf(periodFromAddress()));
    const onPopState = () => {
      if (window.location.pathname === PAGE_PATHS.comparison) {
        const next = periodFromAddress();
        setPeriod(next);
        setMonthDraft(next.month);
      }
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    const request = ++latestRequest.current;
    void getComparison(period).then((result) => {
      if (request !== latestRequest.current) {
        return;
      }
      if (result.ok) {
        setComparison(result.data);
        setError(null);
      } else {
        setComparison(null);
        setError(result.error.message);
      }
    });
    return () => {
      // A request still running when the page closes is not shown either.
      latestRequest.current += 1;
    };
  }, [period]);

  function choose(next: ComparisonPeriod) {
    window.history.pushState(null, "", addressOf(next));
    setPeriod(next);
    setMonthDraft(next.month);
  }

  function changeKind(event: ChangeEvent<HTMLSelectElement>) {
    choose(currentComparison(new Date(), event.target.value as ComparisonKind));
  }

  function changeMonth(event: ChangeEvent<HTMLInputElement>) {
    const month = event.target.value;
    setMonthDraft(month);
    if (isUnitValue("month", month)) {
      choose({ ...period, month });
    }
  }

  return (
    <section aria-labelledby="comparison-heading">
      <h2 id="comparison-heading">{fi.comparison.heading}</h2>
      <p>
        <label>
          {fi.comparison.period}{" "}
          <select value={period.kind} onChange={changeKind}>
            <option value="calendar">{fi.comparison.calendar}</option>
            <option value="mid">{fi.comparison.mid}</option>
          </select>
        </label>{" "}
        <label>
          {fi.comparison.month} <input type="month" value={monthDraft} onChange={changeMonth} />
        </label>
      </p>
      {error && <p role="alert">{error}</p>}
      {comparison !== null && (
        <>
          <p>
            {fi.comparison.covered(
              formatDate(comparison.start_date),
              formatDate(comparison.end_date),
            )}
          </p>
          <p>
            {/* The period of the shown answer, not of the controls (PDF export PC10). */}
            <a
              href={comparisonPdfUrl({ month: comparison.month, kind: comparison.period })}
              download
              className="button"
            >
              {fi.comparison.exportPdf}
            </a>
          </p>
          {comparison.unreviewed_receipts > 0 && (
            <p role="status">{fi.comparison.unreviewed(comparison.unreviewed_receipts)}</p>
          )}
          {comparison.undated_receipts > 0 && (
            <p role="status">{fi.totals.undated(comparison.undated_receipts)}</p>
          )}
          <ComparisonMonthTable comparison={comparison} />
          <p>
            <button
              type="button"
              aria-expanded={isWeeksOpen}
              onClick={() => setIsWeeksOpen(!isWeeksOpen)}
            >
              {isWeeksOpen ? fi.comparison.hideWeeks : fi.comparison.showWeeks}
            </button>
          </p>
          {isWeeksOpen && <ComparisonWeekTable comparison={comparison} />}
        </>
      )}
    </section>
  );
}
