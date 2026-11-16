import { useEffect, useState } from "react";
import { getYearTotals, yearCsvUrl, type YearTotals } from "../api/totals";
import { fi } from "../i18n/fi";
import { ArchiveTotalsTable } from "./ArchiveTotalsTable";

type State =
  { kind: "loading" } | { kind: "shown"; totals: YearTotals } | { kind: "failed"; message: string };

/** The current year's totals per group, category and product, read-only (year with
 * products spec PC4, PC6, PC7). The table is the archived year page's. */
export function YearPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    void getYearTotals().then((result) => {
      if (cancelled) {
        return;
      }
      setState(
        result.ok
          ? { kind: "shown", totals: result.data }
          : { kind: "failed", message: result.error.message },
      );
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const totals = state.kind === "shown" ? state.totals : null;

  return (
    <section aria-labelledby="year-heading">
      <h2 id="year-heading">{totals ? fi.year.title(totals.year) : fi.year.heading}</h2>
      {state.kind === "failed" && <p role="alert">{state.message}</p>}
      {totals && totals.unreviewed > 0 && <p>{fi.year.unreviewed(totals.unreviewed)}</p>}
      {totals && totals.rows.length === 0 && <p>{fi.year.empty(totals.year)}</p>}
      {totals && totals.rows.length > 0 && (
        <>
          <p>
            <a href={yearCsvUrl()} download className="button">
              {fi.archive.exportCsv}
            </a>
          </p>
          <ArchiveTotalsTable totals={totals} />
        </>
      )}
    </section>
  );
}
