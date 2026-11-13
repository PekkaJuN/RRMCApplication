import { useEffect, useState } from "react";
import { archiveCsvUrl, getArchiveTotals, type ArchiveTotals } from "../api/archive";
import { fi } from "../i18n/fi";
import { ArchiveTotalsTable } from "./ArchiveTotalsTable";

interface Props {
  year: number;
}

type State =
  | { kind: "loading" }
  | { kind: "shown"; totals: ArchiveTotals }
  | { kind: "missing" }
  | { kind: "failed"; message: string };

/** One archived year, read-only (archiving PC15). */
export function ArchiveYearPage({ year }: Props) {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    void getArchiveTotals(year).then((result) => {
      if (cancelled) {
        return;
      }
      if (result.ok) {
        setState({ kind: "shown", totals: result.data });
      } else if (result.error.code === "not_found") {
        setState({ kind: "missing" });
      } else {
        setState({ kind: "failed", message: result.error.message });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [year]);

  return (
    <section aria-labelledby="archive-year-heading">
      <h2 id="archive-year-heading">
        {fi.archive.heading} {year}
      </h2>
      {state.kind === "missing" && <p>{fi.archive.notArchived(year)}</p>}
      {state.kind === "failed" && <p role="alert">{state.message}</p>}
      {state.kind === "shown" && (
        <>
          <p>
            <a href={archiveCsvUrl(year)} download className="button">
              {fi.archive.exportCsv}
            </a>
          </p>
          <ArchiveTotalsTable totals={state.totals} />
        </>
      )}
    </section>
  );
}
